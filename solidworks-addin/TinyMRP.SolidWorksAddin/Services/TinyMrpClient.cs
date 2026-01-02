using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using TinyMRP.SolidWorksAddin.Models;

namespace TinyMRP.SolidWorksAddin.Services
{
    public class TinyMrpClient
    {
        private readonly CookieContainer _cookies = new();
        private readonly HttpClient _http;
        private readonly TinyMrpTokenStore _tokenStore;
        private readonly string _filesLocalRoot;
        private readonly string _filesUrlPrefix;
        private readonly string _reservePnEndpoint;
        private string? _csrfToken;
        private string? _authToken;

        public Uri BaseUri { get; }
        public string FilesLocalRoot => _tokenStore.FilesLocalRoot ?? _filesLocalRoot;
        public string FilesUrlPrefix => _tokenStore.FilesUrlPrefix ?? _filesUrlPrefix;

        public TinyMrpClient(Uri baseUri, string filesLocalRoot, string filesUrlPrefix, string reservePnEndpoint, TinyMrpTokenStore tokenStore)
        {
            BaseUri = baseUri;
            _filesLocalRoot = filesLocalRoot;
            _filesUrlPrefix = filesUrlPrefix;
            _reservePnEndpoint = string.IsNullOrWhiteSpace(reservePnEndpoint) ? "/api/pn/reserve" : reservePnEndpoint;
            _tokenStore = tokenStore;
            _authToken = tokenStore.AuthToken;

            var handler = new HttpClientHandler
            {
                CookieContainer = _cookies,
                AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate,
                UseCookies = true,
            };
            _http = new HttpClient(handler)
            {
                BaseAddress = baseUri,
                Timeout = TimeSpan.FromSeconds(120)
            };
        }

        public void PersistSettings(string filesLocalRoot, string filesUrlPrefix)
        {
            _tokenStore.FilesLocalRoot = filesLocalRoot;
            _tokenStore.FilesUrlPrefix = filesUrlPrefix;
        }

        public async Task<LoginResult> LoginAsync(string email, string password, CancellationToken ct = default)
        {
            _csrfToken = await FetchCsrfTokenAsync(ct).ConfigureAwait(false);
            if (string.IsNullOrWhiteSpace(_csrfToken))
            {
                return new LoginResult(false, "No se pudo obtener token CSRF de TinyMRP.");
            }

            var loginUrl = new Uri(BaseUri, "/login?include_auth_token=1");
            var payload = JsonSerializer.Serialize(new { email, password, remember = true });
            var request = new HttpRequestMessage(HttpMethod.Post, loginUrl)
            {
                Content = new StringContent(payload, Encoding.UTF8, "application/json")
            };
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            request.Headers.Add("X-CSRFToken", _csrfToken);
            request.Headers.Add("X-Requested-With", "XMLHttpRequest");

            var response = await _http.SendAsync(request, ct).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return new LoginResult(false, $"Login rechazado: HTTP {(int)response.StatusCode}");
            }

            var content = await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            _authToken = ExtractAuthToken(content) ?? _authToken;
            _tokenStore.AuthToken = _authToken;
            _tokenStore.Email = email;
            _tokenStore.BaseUrl = BaseUri.ToString();

            // Some deployments will rotate the CSRF token after login; refresh it for later POST calls.
            _csrfToken = await FetchCsrfTokenAsync(ct).ConfigureAwait(false);

            return new LoginResult(true, "Autenticado correctamente.");
        }

        public async Task<DocPackOptions?> GetOptionsAsync(string pn, string? rev, bool topLevelOnly, CancellationToken ct = default)
        {
            var qs = new StringBuilder($"/api/docpacks/options?pn={Uri.EscapeDataString(pn)}");
            if (!string.IsNullOrWhiteSpace(rev))
            {
                qs.Append($"&rev={Uri.EscapeDataString(rev)}");
            }
            qs.Append(topLevelOnly ? "&depth=top" : "&depth=full");

            var request = new HttpRequestMessage(HttpMethod.Get, new Uri(BaseUri, qs.ToString()));
            AddAuthHeaders(request, requiresCsrf: false);

            var response = await _http.SendAsync(request, ct).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                return new DocPackOptions
                {
                    FileTypes = root.TryGetProperty("file_types", out var ft) && ft.ValueKind == JsonValueKind.Array
                        ? ft.EnumerateArray().Select(e => e.GetString() ?? string.Empty).Where(s => !string.IsNullOrWhiteSpace(s)).ToList()
                        : new List<string>(),
                    Processes = root.TryGetProperty("processes", out var pr) && pr.ValueKind == JsonValueKind.Array
                        ? pr.EnumerateArray().Select(e => e.GetString() ?? string.Empty).Where(s => !string.IsNullOrWhiteSpace(s)).ToList()
                        : new List<string>(),
                };
            }
            catch
            {
                return null;
            }
        }

        public async Task<DocPackBuildResult?> BuildDocPackAsync(DocPackRequest requestModel, bool overwriteExisting, CancellationToken ct = default)
        {
            if (string.IsNullOrWhiteSpace(requestModel.PartNumber))
            {
                throw new ArgumentException("Part number requerido", nameof(requestModel));
            }

            var payload = new Dictionary<string, object?>
            {
                ["pn"] = requestModel.PartNumber,
                ["rev"] = requestModel.Revision,
                ["depth"] = requestModel.Depth,
                ["include_consumed"] = requestModel.IncludeConsumed,
                ["classified"] = requestModel.Classified,
                ["process_mode"] = requestModel.ProcessMode,
                ["processes"] = requestModel.Processes,
                ["file_types"] = requestModel.FileTypes,
                ["excel_bom"] = requestModel.ExcelBom,
                ["pdf_binder"] = requestModel.PdfBinder,
                ["visual_list"] = requestModel.VisualList,
                ["selected_files"] = requestModel.SelectedFiles,
                ["fabrication_pack"] = requestModel.FabricationPack,
                ["binder_add_index"] = requestModel.BinderAddIndex,
                ["binder_add_datasheets"] = requestModel.BinderAddDatasheets,
                ["binder_page_numbers"] = requestModel.BinderPageNumbers,
                ["stamp_quote"] = requestModel.StampQuote,
                ["stamp_confidential"] = requestModel.StampConfidential,
                ["stamp_approved"] = requestModel.StampApproved,
                ["stamp_wip"] = requestModel.StampWip,
                ["stamp_inprogress"] = requestModel.StampInProgress,
            };

            var json = JsonSerializer.Serialize(payload);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var req = new HttpRequestMessage(HttpMethod.Post, new Uri(BaseUri, "/api/docpacks/build"))
            {
                Content = content
            };
            AddAuthHeaders(req, requiresCsrf: true);

            var resp = await SendWithCsrfRetryAsync(req, ct).ConfigureAwait(false);
            if (resp == null || !resp.IsSuccessStatusCode)
            {
                return null;
            }

            var data = await resp.Content.ReadAsByteArrayAsync(ct).ConfigureAwait(false);
            var filename = GetAttachmentName(resp) ?? $"{requestModel.PartNumber}_docpack.zip";
            var localPath = SaveToLocalRoot(filename, data, overwriteExisting);
            var httpUrl = BuildHttpUrl(localPath);

            return new DocPackBuildResult
            {
                LocalPath = localPath,
                HttpUrl = httpUrl,
                FileName = filename
            };
        }

        public async Task<ReservedPnResponse?> ReservePnAsync(string? hint, CancellationToken ct = default)
        {
            var payload = JsonSerializer.Serialize(new { hint });
            var req = new HttpRequestMessage(HttpMethod.Post, new Uri(BaseUri, _reservePnEndpoint))
            {
                Content = new StringContent(payload, Encoding.UTF8, "application/json")
            };
            AddAuthHeaders(req, requiresCsrf: true);

            var resp = await SendWithCsrfRetryAsync(req, ct).ConfigureAwait(false);
            if (resp == null || !resp.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                return new ReservedPnResponse
                {
                    PartNumber = root.TryGetProperty("pn", out var pn) ? pn.GetString() : root.TryGetProperty("part_number", out var pn2) ? pn2.GetString() : null,
                    Revision = root.TryGetProperty("rev", out var rev) ? rev.GetString() : root.TryGetProperty("revision", out var rev2) ? rev2.GetString() : null,
                    Message = root.TryGetProperty("message", out var msg) ? msg.GetString() : null
                };
            }
            catch
            {
                return null;
            }
        }

        private async Task<HttpResponseMessage?> SendWithCsrfRetryAsync(HttpRequestMessage req, CancellationToken ct)
        {
            string? body = null;
            string? media = null;
            if (req.Content != null)
            {
                body = await req.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
                media = req.Content.Headers.ContentType?.MediaType;
            }

            var response = await _http.SendAsync(req, ct).ConfigureAwait(false);
            if (response.StatusCode == HttpStatusCode.Forbidden)
            {
                _csrfToken = await FetchCsrfTokenAsync(ct).ConfigureAwait(false);
                response.Dispose();

                var retry = new HttpRequestMessage(req.Method, req.RequestUri);
                foreach (var h in req.Headers)
                {
                    retry.Headers.TryAddWithoutValidation(h.Key, h.Value);
                }
                if (body != null)
                {
                    retry.Content = new StringContent(body, Encoding.UTF8, media ?? "application/json");
                }
                AddAuthHeaders(retry, requiresCsrf: true);
                response = await _http.SendAsync(retry, ct).ConfigureAwait(false);
            }
            return response;
        }

        private void AddAuthHeaders(HttpRequestMessage req, bool requiresCsrf)
        {
            if (!string.IsNullOrWhiteSpace(_authToken))
            {
                req.Headers.Remove("Authentication-Token");
                req.Headers.Add("Authentication-Token", _authToken);
            }

            if (requiresCsrf)
            {
                if (string.IsNullOrWhiteSpace(_csrfToken))
                {
                    _csrfToken = FetchCsrfTokenAsync().GetAwaiter().GetResult();
                }
                if (!string.IsNullOrWhiteSpace(_csrfToken))
                {
                    req.Headers.Remove("X-CSRFToken");
                    req.Headers.Add("X-CSRFToken", _csrfToken);
                    req.Headers.Add("X-Requested-With", "XMLHttpRequest");
                }
            }
        }

        private async Task<string?> FetchCsrfTokenAsync(CancellationToken ct = default)
        {
            try
            {
                var resp = await _http.GetAsync(new Uri(BaseUri, "/login"), ct).ConfigureAwait(false);
                var html = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
                return ExtractCsrf(html);
            }
            catch
            {
                return null;
            }
        }

        private string? ExtractAuthToken(string json)
        {
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                if (root.TryGetProperty("response", out var resp))
                {
                    if (resp.TryGetProperty("user", out var user) && user.TryGetProperty("authentication_token", out var tok))
                    {
                        return tok.GetString();
                    }
                    if (resp.TryGetProperty("authentication_token", out var direct))
                    {
                        return direct.GetString();
                    }
                }
            }
            catch
            {
                // not JSON
            }
            return null;
        }

        private string? ExtractCsrf(string html)
        {
            if (string.IsNullOrWhiteSpace(html))
            {
                return null;
            }

            var match = Regex.Match(html, "csrf_token\\\"?\\s+value=\\\"([^\\\"]+)\\\"", RegexOptions.IgnoreCase);
            return match.Success ? match.Groups[1].Value : null;
        }

        private string SaveToLocalRoot(string filename, byte[] data, bool overwrite)
        {
            var basePath = _tokenStore.FilesLocalRoot ?? _filesLocalRoot;
            if (string.IsNullOrWhiteSpace(basePath))
            {
                throw new InvalidOperationException("FILES_LOCAL_ROOT no está configurado.");
            }

            var targetDir = Path.Combine(basePath, "docpacks");
            Directory.CreateDirectory(targetDir);
            var fullPath = Path.Combine(targetDir, filename);
            if (File.Exists(fullPath) && !overwrite)
            {
                var withoutExt = Path.GetFileNameWithoutExtension(filename);
                var ext = Path.GetExtension(filename);
                fullPath = Path.Combine(targetDir, $"{withoutExt}_{DateTime.Now:yyyyMMddHHmmss}{ext}");
            }

            File.WriteAllBytes(fullPath, data);
            return fullPath;
        }

        private string? BuildHttpUrl(string localPath)
        {
            var basePath = _tokenStore.FilesLocalRoot ?? _filesLocalRoot;
            var prefix = _tokenStore.FilesUrlPrefix ?? _filesUrlPrefix;
            if (string.IsNullOrWhiteSpace(basePath) || string.IsNullOrWhiteSpace(prefix))
            {
                return null;
            }

            var relPath = MakeRelativePath(basePath, localPath).Replace(Path.DirectorySeparatorChar, '/');
            return CombineUrl(prefix, relPath);
        }

        private static string CombineUrl(string prefix, string relative)
        {
            prefix = prefix.TrimEnd('/') + "/";
            relative = relative.TrimStart('/');
            return prefix + relative;
        }

        private string MakeRelativePath(string basePath, string fullPath)
        {
            try
            {
                var baseUri = new Uri(AppendDirectorySeparatorChar(basePath));
                var fullUri = new Uri(fullPath);
                return Uri.UnescapeDataString(baseUri.MakeRelativeUri(fullUri).ToString());
            }
            catch
            {
                return Path.GetFileName(fullPath);
            }
        }

        private static string AppendDirectorySeparatorChar(string path)
        {
            if (!path.EndsWith(Path.DirectorySeparatorChar.ToString()))
            {
                return path + Path.DirectorySeparatorChar;
            }
            return path;
        }

        private string? GetAttachmentName(HttpResponseMessage resp)
        {
            if (resp.Content?.Headers?.ContentDisposition != null)
            {
                return resp.Content.Headers.ContentDisposition.FileName?.Trim('"');
            }

            if (resp.Headers.TryGetValues("Content-Disposition", out var values))
            {
                var raw = values.FirstOrDefault();
                if (!string.IsNullOrWhiteSpace(raw))
                {
                    var match = Regex.Match(raw, "filename=\"?([^\";]+)\"?");
                    if (match.Success)
                    {
                        return match.Groups[1].Value;
                    }
                }
            }
            return null;
        }
    }

    public record LoginResult(bool Success, string Message);
}
