using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Web.Script.Serialization;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class NumberingApiClient
    {
        private const int DefaultTimeoutSeconds = 15;
        private const int MaxRetries = 1;
        private const int ResponseSnippetLimit = 200;

        private readonly TinyMrpConfig _config;
        private readonly JavaScriptSerializer _serializer = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        public NumberingApiClient(TinyMrpConfig config)
        {
            _config = config;
            EnsureTls12Compatibility();
        }

        public ApiResponse HealthCheck()
        {
            return Send("GET", "/api/health", null, includeAuth: false);
        }

        public ApiResponse ListSchemes(out List<NumberingSchemeDefinition> schemes)
        {
            schemes = new List<NumberingSchemeDefinition>();
            ApiResponse response = Send("GET", "/api/numbering/schemes", null);
            if (!response.Ok)
            {
                return response;
            }

            Dictionary<string, object> dict = response.Data;
            foreach (Dictionary<string, object> schemeData in NumberingJson.GetDictList(dict, "schemes"))
            {
                schemes.Add(NumberingSchemeDefinition.FromDictionary(schemeData));
            }
            return response;
        }

        public ApiResponse ValidateScheme(NumberingSchemeDefinition scheme)
        {
            return Send("POST", "/api/numbering/schemes/validate", scheme.ToPayload());
        }

        public ApiResponse CreateScheme(NumberingSchemeDefinition scheme)
        {
            return Send("POST", "/api/numbering/schemes", scheme.ToPayload());
        }

        public ApiResponse UpdateScheme(NumberingSchemeDefinition scheme)
        {
            if (string.IsNullOrWhiteSpace(scheme.Id))
            {
                return ApiResponse.Failure("missing_scheme", "Scheme id is required.");
            }
            return Send("PUT", "/api/numbering/schemes/" + scheme.Id, scheme.ToPayload());
        }

        public ApiResponse DeleteScheme(string schemeId)
        {
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                return ApiResponse.Failure("missing_scheme", "Scheme id is required.");
            }
            return Send("DELETE", "/api/numbering/schemes/" + schemeId, null);
        }

        public ApiResponse Preview(string schemeId, Dictionary<string, string> context)
        {
            var payload = new Dictionary<string, object>
            {
                ["scheme_id"] = schemeId ?? string.Empty,
                ["context"] = context ?? new Dictionary<string, string>(),
            };
            return Send("POST", "/api/numbering/preview", payload);
        }

        public ApiResponse AuthCheck()
        {
            return Send("GET", "/api/auth/check", null);
        }

        public ApiResponse GetUserSettings(out UserSettingsDefinition settings)
        {
            settings = null;
            ApiResponse response = Send("GET", "/api/me/settings", null);
            if (!response.Ok)
            {
                return response;
            }

            Dictionary<string, object> dict = response.Data;
            Dictionary<string, object> settingsDict = NumberingJson.GetDict(dict, "settings");
            if (settingsDict != null)
            {
                settings = UserSettingsDefinition.FromDict(settingsDict);
            }
            return response;
        }

        public ApiResponse SaveUserSettings(UserSettingsDefinition settings)
        {
            var payload = settings != null ? settings.ToPayload() : new Dictionary<string, object>();
            return Send("PUT", "/api/me/settings", payload);
        }

        public ApiResponse Allocate(string schemeId, Dictionary<string, string> context, string action, string existingPartNumber, bool createPart, Dictionary<string, object> cadRef)
        {
            var payload = new Dictionary<string, object>
            {
                ["scheme_id"] = schemeId ?? string.Empty,
                ["context"] = context ?? new Dictionary<string, string>(),
                ["requested_revision_action"] = action ?? "new_part",
                ["existing_part_number"] = existingPartNumber ?? string.Empty,
                ["create_part_if_missing"] = createPart,
            };
            if (cadRef != null)
            {
                payload["cad_ref"] = cadRef;
            }
            return Send("POST", "/api/numbering/allocate", payload);
        }

        private ApiResponse Send(string method, string path, object payload, bool includeAuth = true)
        {
            string baseUrl = BuildBaseUrl();
            if (string.IsNullOrWhiteSpace(baseUrl))
            {
                return ApiResponse.Failure("missing_backend", "Backend URL is not configured.");
            }

            string url = baseUrl + path;
            string json = payload != null ? _serializer.Serialize(payload) : null;
            Exception lastError = null;

            for (int attempt = 0; attempt <= MaxRetries; attempt++)
            {
                try
                {
                    using (var client = CreateClient())
                    using (var request = new HttpRequestMessage(new HttpMethod(method), url))
                    {
                        if (json != null)
                        {
                            request.Content = new StringContent(json, Encoding.UTF8, "application/json");
                        }

                        if (includeAuth)
                        {
                            AddAuthHeaders(request);
                        }
                        HttpResponseMessage response = client.SendAsync(request).Result;
                        string responseText = response.Content.ReadAsStringAsync().Result;
                        string finalUrl = response.RequestMessage != null && response.RequestMessage.RequestUri != null
                            ? response.RequestMessage.RequestUri.ToString()
                            : url;
                        return ParseResponse(responseText, response.IsSuccessStatusCode, (int)response.StatusCode, finalUrl);
                    }
                }
                catch (Exception ex)
                {
                    lastError = ex;
                }
            }

            var failure = ApiResponse.Failure("request_failed", lastError != null ? lastError.Message : "Request failed.");
            failure.RequestUrl = url;
            return failure;
        }

        private HttpClient CreateClient()
        {
            EnsureTls12Compatibility();
            var client = new HttpClient();
            client.Timeout = TimeSpan.FromSeconds(DefaultTimeoutSeconds);
            return client;
        }

        private void AddAuthHeaders(HttpRequestMessage request)
        {
            string token = (_config.AuthToken ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(token))
            {
                return;
            }

            AddAuthHeaders(request, token);
        }

        private string BuildBaseUrl()
        {
            string url = NormalizeBaseUrl(_config != null ? _config.BackendUrl : null);
            if (!string.IsNullOrWhiteSpace(url))
            {
                return url;
            }

            return NormalizeBaseUrl(_config != null ? _config.WebLink : null);
        }

        private ApiResponse ParseResponse(string json, bool success, int statusCode, string requestUrl)
        {
            var response = new ApiResponse
            {
                Ok = false,
                Data = new Dictionary<string, object>(),
                StatusCode = statusCode,
                RequestUrl = requestUrl,
                ResponseSnippet = CreateSnippet(json),
            };

            if (string.IsNullOrWhiteSpace(json))
            {
                if (success)
                {
                    response.Ok = true;
                    return response;
                }

                response.ErrorCode = "empty_response";
                response.ErrorMessage = "Empty response from server.";
                return response;
            }

            string trimmed = json.Trim();
            if (trimmed.StartsWith("<", StringComparison.Ordinal))
            {
                response.ErrorCode = "invalid_response";
                response.ErrorMessage = "Server returned HTML, not the JSON API. Check the Backend URL and reverse proxy path.";
                response.ResponseIsHtml = true;
                if (!string.IsNullOrWhiteSpace(response.ResponseSnippet))
                {
                    response.ErrorDetails.Add(response.ResponseSnippet);
                }
                return response;
            }

            Dictionary<string, object> dict = null;
            try
            {
                object parsed = _serializer.DeserializeObject(json);
                dict = parsed as Dictionary<string, object>;
            }
            catch (Exception ex)
            {
                response.ErrorCode = "invalid_response";
                response.ErrorMessage = "Invalid JSON response: " + ex.Message;
                if (!string.IsNullOrWhiteSpace(response.ResponseSnippet))
                {
                    response.ErrorDetails.Add(response.ResponseSnippet);
                }
                return response;
            }
            if (dict == null)
            {
                if (success)
                {
                    response.Ok = true;
                    return response;
                }

                response.ErrorCode = "invalid_response";
                response.ErrorMessage = "Invalid response from server.";
                return response;
            }

            response.Data = dict;
            bool ok = NumberingJson.GetBool(dict, "ok", success);
            if (ok)
            {
                response.Ok = true;
                return response;
            }

            string code = "request_failed";
            string message = "Request failed.";
            Dictionary<string, object> err = NumberingJson.GetDict(dict, "error");
            if (err != null)
            {
                code = NumberingJson.GetString(err, "code") ?? code;
                message = NumberingJson.GetString(err, "message") ?? message;
                foreach (string detail in NumberingJson.GetStringList(err, "details"))
                {
                    response.ErrorDetails.Add(detail);
                }
            }
            else
            {
                string stringError = NumberingJson.GetString(dict, "error");
                if (!string.IsNullOrWhiteSpace(stringError))
                {
                    code = stringError;
                    message = GetDefaultErrorMessage(stringError, statusCode);
                }
                else if (statusCode == 401 || statusCode == 403)
                {
                    code = "unauthorized";
                    message = GetDefaultErrorMessage(code, statusCode);
                }
            }

            response.ErrorCode = code ?? "request_failed";
            response.ErrorMessage = message ?? "Request failed.";
            if (response.ErrorDetails.Count == 0 && !success && !string.IsNullOrWhiteSpace(response.ResponseSnippet))
            {
                response.ErrorDetails.Add(response.ResponseSnippet);
            }
            return response;
        }

        internal static string NormalizeBaseUrl(string rawUrl)
        {
            string value = (rawUrl ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value))
            {
                return string.Empty;
            }

            if (!HasExplicitScheme(value))
            {
                string host = ExtractHostToken(value);
                string scheme = IsDevelopmentHost(host) ? "http://" : "https://";
                value = scheme + NormalizeAuthorityForUri(value);
            }

            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri))
            {
                return value.TrimEnd('/');
            }

            string normalized = uri.GetLeftPart(UriPartial.Authority);
            string path = NormalizeApiBasePath(uri.AbsolutePath);
            if (!string.IsNullOrWhiteSpace(path))
            {
                normalized += path;
            }

            return normalized.TrimEnd('/');
        }

        internal static void AddAuthHeaders(HttpRequestMessage request, string token)
        {
            if (request == null)
            {
                return;
            }

            string trimmed = (token ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(trimmed))
            {
                return;
            }

            request.Headers.Add("Authentication-Token", trimmed);
            request.Headers.Add("X-Auth-Token", trimmed);
            request.Headers.Add("Authorization", "Bearer " + trimmed);
        }

        internal static void EnsureTls12Compatibility()
        {
            try
            {
                ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            }
            catch
            {
                // Keep the default platform behavior if TLS flags cannot be updated.
            }
        }

        private static string GetDefaultErrorMessage(string code, int statusCode)
        {
            if (string.Equals(code, "token_required", StringComparison.OrdinalIgnoreCase))
            {
                return "Auth token is missing.";
            }
            if (string.Equals(code, "invalid_token", StringComparison.OrdinalIgnoreCase))
            {
                return "Auth token is invalid.";
            }
            if (statusCode == 401 || statusCode == 403 || string.Equals(code, "unauthorized", StringComparison.OrdinalIgnoreCase))
            {
                return "Authentication required. Set AuthToken in Configuration.";
            }
            return "Request failed.";
        }

        private static bool HasExplicitScheme(string value)
        {
            return value.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
                || value.StartsWith("https://", StringComparison.OrdinalIgnoreCase);
        }

        private static string NormalizeAuthorityForUri(string value)
        {
            string trimmed = (value ?? string.Empty).Trim();
            int slashIndex = trimmed.IndexOf('/');
            string authority = slashIndex >= 0 ? trimmed.Substring(0, slashIndex) : trimmed;
            string suffix = slashIndex >= 0 ? trimmed.Substring(slashIndex) : string.Empty;
            if (!authority.StartsWith("[", StringComparison.Ordinal) && CountChar(authority, ':') > 1)
            {
                authority = "[" + authority + "]";
            }
            return authority + suffix;
        }

        private static string ExtractHostToken(string value)
        {
            string authority = (value ?? string.Empty).Trim();
            int slashIndex = authority.IndexOf('/');
            if (slashIndex >= 0)
            {
                authority = authority.Substring(0, slashIndex);
            }

            if (authority.StartsWith("[", StringComparison.Ordinal))
            {
                int endBracket = authority.IndexOf(']');
                if (endBracket > 1)
                {
                    return authority.Substring(1, endBracket - 1);
                }
            }

            if (CountChar(authority, ':') > 1)
            {
                return authority;
            }

            int colonIndex = authority.IndexOf(':');
            if (colonIndex >= 0)
            {
                authority = authority.Substring(0, colonIndex);
            }

            return authority.Trim().Trim('[', ']');
        }

        private static bool IsDevelopmentHost(string host)
        {
            string normalized = (host ?? string.Empty).Trim().Trim('[', ']').ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(normalized))
            {
                return false;
            }

            if (string.Equals(normalized, "localhost", StringComparison.Ordinal)
                || string.Equals(normalized, "127.0.0.1", StringComparison.Ordinal)
                || string.Equals(normalized, "::1", StringComparison.Ordinal))
            {
                return true;
            }

            return normalized.EndsWith(".local", StringComparison.Ordinal)
                || normalized.EndsWith(".localdomain", StringComparison.Ordinal)
                || normalized.EndsWith(".localhost", StringComparison.Ordinal)
                || normalized.EndsWith(".test", StringComparison.Ordinal)
                || normalized.EndsWith(".test.local", StringComparison.Ordinal);
        }

        private static string NormalizeApiBasePath(string path)
        {
            string normalized = (path ?? string.Empty).Trim().Replace('\\', '/');
            if (string.IsNullOrWhiteSpace(normalized) || normalized == "/")
            {
                return string.Empty;
            }

            normalized = normalized.TrimEnd('/');
            while (!string.IsNullOrWhiteSpace(normalized))
            {
                if (normalized.Equals("/api/numbering", StringComparison.OrdinalIgnoreCase))
                {
                    return string.Empty;
                }
                if (normalized.EndsWith("/api/numbering", StringComparison.OrdinalIgnoreCase))
                {
                    normalized = normalized.Substring(0, normalized.Length - "/api/numbering".Length).TrimEnd('/');
                    continue;
                }
                if (normalized.Equals("/api", StringComparison.OrdinalIgnoreCase))
                {
                    return string.Empty;
                }
                if (normalized.EndsWith("/api", StringComparison.OrdinalIgnoreCase))
                {
                    normalized = normalized.Substring(0, normalized.Length - "/api".Length).TrimEnd('/');
                    continue;
                }
                break;
            }

            return normalized;
        }

        private static string CreateSnippet(string value)
        {
            string trimmed = (value ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(trimmed))
            {
                return string.Empty;
            }
            if (trimmed.Length <= ResponseSnippetLimit)
            {
                return trimmed;
            }
            return trimmed.Substring(0, ResponseSnippetLimit) + "...";
        }

        private static int CountChar(string value, char target)
        {
            int count = 0;
            foreach (char c in value ?? string.Empty)
            {
                if (c == target)
                {
                    count++;
                }
            }
            return count;
        }
    }

    internal sealed class ApiResponse
    {
        public bool Ok { get; set; }
        public Dictionary<string, object> Data { get; set; }
        public string ErrorCode { get; set; }
        public string ErrorMessage { get; set; }
        public int StatusCode { get; set; }
        public string RequestUrl { get; set; }
        public string ResponseSnippet { get; set; }
        public bool ResponseIsHtml { get; set; }
        public List<string> ErrorDetails { get; } = new List<string>();

        public static ApiResponse Failure(string code, string message)
        {
            return new ApiResponse
            {
                Ok = false,
                ErrorCode = code,
                ErrorMessage = message,
                Data = new Dictionary<string, object>()
            };
        }
    }
}
