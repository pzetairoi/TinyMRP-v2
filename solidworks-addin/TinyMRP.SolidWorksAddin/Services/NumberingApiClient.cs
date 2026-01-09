using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Web.Script.Serialization;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class NumberingApiClient
    {
        private const int DefaultTimeoutSeconds = 15;
        private const int MaxRetries = 1;

        private readonly TinyMrpConfig _config;
        private readonly JavaScriptSerializer _serializer = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        public NumberingApiClient(TinyMrpConfig config)
        {
            _config = config;
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

        private ApiResponse Send(string method, string path, object payload)
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

                        AddAuthHeaders(request);
                        HttpResponseMessage response = client.SendAsync(request).Result;
                        string responseText = response.Content.ReadAsStringAsync().Result;
                        return ParseResponse(responseText, response.IsSuccessStatusCode, (int)response.StatusCode);
                    }
                }
                catch (Exception ex)
                {
                    lastError = ex;
                }
            }

            return ApiResponse.Failure("request_failed", lastError != null ? lastError.Message : "Request failed.");
        }

        private HttpClient CreateClient()
        {
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

            request.Headers.Add("Authentication-Token", token);
            request.Headers.Add("X-Auth-Token", token);
            request.Headers.Add("Authorization", "Bearer " + token);
        }

        private string BuildBaseUrl()
        {
            string url = _config.BackendUrl;
            if (string.IsNullOrWhiteSpace(url))
            {
                url = _config.WebLink;
            }

            url = (url ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(url))
            {
                return string.Empty;
            }

            if (!url.Contains("://"))
            {
                url = "http://" + url;
            }

            return url.TrimEnd('/');
        }

        private ApiResponse ParseResponse(string json, bool success, int statusCode)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return success
                    ? new ApiResponse { Ok = true, Data = new Dictionary<string, object>() }
                    : ApiResponse.Failure("empty_response", "Empty response from server.");
            }

            string trimmed = json.Trim();
            if (!success && (statusCode == 401 || statusCode == 403))
            {
                return ApiResponse.Failure("unauthorized", "Authentication required. Set AuthToken in Configuration.");
            }

            if (trimmed.StartsWith("<", StringComparison.Ordinal))
            {
                return ApiResponse.Failure("invalid_response",
                    "Server returned HTML, not JSON. Check AuthToken and backend URL.");
            }

            Dictionary<string, object> dict = null;
            try
            {
                object parsed = _serializer.DeserializeObject(json);
                dict = parsed as Dictionary<string, object>;
            }
            catch (Exception ex)
            {
                string snippet = trimmed.Length > 200 ? trimmed.Substring(0, 200) + "..." : trimmed;
                var failure = ApiResponse.Failure("invalid_response", "Invalid JSON response: " + ex.Message);
                if (!string.IsNullOrWhiteSpace(snippet))
                {
                    failure.ErrorDetails.Add(snippet);
                }
                return failure;
            }
            if (dict == null)
            {
                return success
                    ? new ApiResponse { Ok = true, Data = new Dictionary<string, object>() }
                    : ApiResponse.Failure("invalid_response", "Invalid response from server.");
            }

            bool ok = NumberingJson.GetBool(dict, "ok", success);
            if (ok)
            {
                return new ApiResponse { Ok = true, Data = dict };
            }

            Dictionary<string, object> err = NumberingJson.GetDict(dict, "error");
            string code = err != null ? NumberingJson.GetString(err, "code") : "request_failed";
            string message = err != null ? NumberingJson.GetString(err, "message") : "Request failed.";
            var response = ApiResponse.Failure(code ?? "request_failed", message ?? "Request failed.");
            foreach (string detail in NumberingJson.GetStringList(err, "details"))
            {
                response.ErrorDetails.Add(detail);
            }
            return response;
        }
    }

    internal sealed class ApiResponse
    {
        public bool Ok { get; set; }
        public Dictionary<string, object> Data { get; set; }
        public string ErrorCode { get; set; }
        public string ErrorMessage { get; set; }
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
