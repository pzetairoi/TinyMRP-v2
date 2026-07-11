using System;
using System.Collections;
using System.Collections.Generic;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class NumberingSchemeDefinition
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public bool IsActive { get; set; }
        public bool IsPreset { get; set; }
        public bool IsRecommended { get; set; }
        public string Visibility { get; set; }
        public string Separator { get; set; }
        public string ScopeMode { get; set; }
        public List<string> ScopeKeys { get; set; } = new List<string>();
        public List<NumberingSegmentDefinition> PatternSegments { get; set; } = new List<NumberingSegmentDefinition>();
        public SequenceSettings Seq { get; set; } = new SequenceSettings();
        public RevisionSettings Revision { get; set; } = new RevisionSettings();
        public ValidationRules ValidationRules { get; set; } = new ValidationRules();

        public override string ToString()
        {
            return string.IsNullOrWhiteSpace(Name) ? "(unnamed scheme)" : Name;
        }

        public Dictionary<string, object> ToPayload()
        {
            var payload = new Dictionary<string, object>
            {
                ["name"] = Name ?? string.Empty,
                ["description"] = Description ?? string.Empty,
                ["is_active"] = IsActive,
                ["is_preset"] = IsPreset,
                ["is_recommended"] = IsRecommended,
                ["visibility"] = Visibility ?? "advanced_only",
                ["separator"] = Separator ?? "-",
                ["scope_mode"] = ScopeMode ?? "global",
                ["scope_keys"] = ScopeKeys ?? new List<string>(),
                ["seq"] = Seq.ToPayload(),
                ["revision"] = Revision.ToPayload(),
                ["validation_rules"] = ValidationRules.ToPayload(),
            };

            var segments = new List<Dictionary<string, object>>();
            foreach (NumberingSegmentDefinition segment in PatternSegments)
            {
                segments.Add(segment.ToPayload());
            }
            payload["pattern_segments"] = segments;
            return payload;
        }

        public static NumberingSchemeDefinition FromDictionary(Dictionary<string, object> data)
        {
            var scheme = new NumberingSchemeDefinition
            {
                Id = NumberingJson.GetString(data, "id"),
                Name = NumberingJson.GetString(data, "name"),
                Description = NumberingJson.GetString(data, "description"),
                IsActive = NumberingJson.GetBool(data, "is_active", true),
                IsPreset = NumberingJson.GetBool(data, "is_preset", false),
                IsRecommended = NumberingJson.GetBool(data, "is_recommended", false),
                Visibility = NumberingJson.GetString(data, "visibility") ?? "advanced_only",
                Separator = NumberingJson.GetString(data, "separator") ?? "-",
                ScopeMode = NumberingJson.GetString(data, "scope_mode") ?? "global",
                ScopeKeys = NumberingJson.GetStringList(data, "scope_keys"),
            };

            Dictionary<string, object> seq = NumberingJson.GetDict(data, "seq");
            if (seq != null)
            {
                scheme.Seq = SequenceSettings.FromDict(seq);
            }
            Dictionary<string, object> rev = NumberingJson.GetDict(data, "revision");
            if (rev != null)
            {
                scheme.Revision = RevisionSettings.FromDict(rev);
            }
            Dictionary<string, object> rules = NumberingJson.GetDict(data, "validation_rules");
            if (rules != null)
            {
                scheme.ValidationRules = ValidationRules.FromDict(rules);
            }

            foreach (Dictionary<string, object> seg in NumberingJson.GetDictList(data, "pattern_segments"))
            {
                scheme.PatternSegments.Add(NumberingSegmentDefinition.FromDict(seg));
            }

            return scheme;
        }
    }

    internal sealed class NumberingSegmentDefinition
    {
        public string Kind { get; set; }
        public string Value { get; set; }
        public string Field { get; set; }
        public string Casing { get; set; }
        public int? PadLeft { get; set; }
        public string PadChar { get; set; }
        public int? Padding { get; set; }
        public int? Base { get; set; }
        public int? StartAt { get; set; }
        public bool AutoCounter { get; set; }
        public string Fmt { get; set; }

        public override string ToString()
        {
            switch ((Kind ?? string.Empty).ToLowerInvariant())
            {
                case "literal":
                    return "Literal: " + (Value ?? string.Empty);
                case "field":
                    return "Field: " + (Field ?? string.Empty);
                case "seq":
                    return string.Format(
                        "Seq: {0}, start {1}, pad {2}",
                        AutoCounter ? "auto" : "manual",
                        StartAt.HasValue ? StartAt.Value.ToString() : "default",
                        Padding.HasValue ? Padding.Value.ToString() : "default");
                case "date":
                    return "Date: " + (Fmt ?? string.Empty);
                default:
                    return Kind ?? "(segment)";
            }
        }

        public Dictionary<string, object> ToPayload()
        {
            var payload = new Dictionary<string, object>
            {
                ["kind"] = (Kind ?? string.Empty).ToLowerInvariant()
            };

            switch ((Kind ?? string.Empty).ToLowerInvariant())
            {
                case "literal":
                    payload["value"] = Value ?? string.Empty;
                    break;
                case "field":
                    payload["field"] = Field ?? string.Empty;
                    if (!string.IsNullOrWhiteSpace(Casing))
                    {
                        payload["casing"] = Casing.ToLowerInvariant();
                    }
                    if (PadLeft.HasValue)
                    {
                        payload["pad_left"] = PadLeft.Value;
                    }
                    if (!string.IsNullOrWhiteSpace(PadChar))
                    {
                        payload["pad_char"] = PadChar;
                    }
                    break;
                case "seq":
                    if (Padding.HasValue)
                    {
                        payload["padding"] = Padding.Value;
                    }
                    if (Base.HasValue)
                    {
                        payload["base"] = Base.Value;
                    }
                    if (StartAt.HasValue)
                    {
                        payload["start_at"] = StartAt.Value;
                    }
                    if (AutoCounter)
                    {
                        payload["auto_counter"] = true;
                    }
                    break;
                case "date":
                    payload["fmt"] = Fmt ?? string.Empty;
                    break;
            }

            return payload;
        }

        public static NumberingSegmentDefinition FromDict(Dictionary<string, object> data)
        {
            return new NumberingSegmentDefinition
            {
                Kind = NumberingJson.GetString(data, "kind"),
                Value = NumberingJson.GetString(data, "value"),
                Field = NumberingJson.GetString(data, "field"),
                Casing = NumberingJson.GetString(data, "casing"),
                PadLeft = NumberingJson.GetNullableInt(data, "pad_left"),
                PadChar = NumberingJson.GetString(data, "pad_char"),
                Padding = NumberingJson.GetNullableInt(data, "padding"),
                Base = NumberingJson.GetNullableInt(data, "base"),
                StartAt = NumberingJson.GetNullableInt(data, "start_at"),
                AutoCounter = NumberingJson.GetBool(data, "auto_counter", false),
                Fmt = NumberingJson.GetString(data, "fmt"),
            };
        }
    }

    internal sealed class SequenceSettings
    {
        public int Padding { get; set; } = 6;
        public int Base { get; set; } = 10;
        public int StartAt { get; set; } = 1;
        public string ResetPolicy { get; set; } = "never";

        public Dictionary<string, object> ToPayload()
        {
            return new Dictionary<string, object>
            {
                ["padding"] = Padding,
                ["base"] = Base,
                ["start_at"] = StartAt,
                ["reset_policy"] = ResetPolicy ?? "never"
            };
        }

        public static SequenceSettings FromDict(Dictionary<string, object> data)
        {
            return new SequenceSettings
            {
                Padding = NumberingJson.GetInt(data, "padding", 6),
                Base = NumberingJson.GetInt(data, "base", 10),
                StartAt = NumberingJson.GetInt(data, "start_at", 1),
                ResetPolicy = NumberingJson.GetString(data, "reset_policy") ?? "never",
            };
        }
    }

    internal sealed class RevisionSettings
    {
        // Default: no revision. Parts without a revision stay revision-less; "A" is only
        // ever applied when a scheme explicitly selects the alpha policy.
        public string Policy { get; set; } = "none";
        public string Start { get; set; } = string.Empty;

        public Dictionary<string, object> ToPayload()
        {
            return new Dictionary<string, object>
            {
                ["policy"] = Policy ?? "none",
                ["start"] = Start ?? string.Empty
            };
        }

        public static RevisionSettings FromDict(Dictionary<string, object> data)
        {
            return new RevisionSettings
            {
                Policy = NumberingJson.GetString(data, "policy") ?? "none",
                Start = NumberingJson.GetString(data, "start") ?? string.Empty,
            };
        }
    }

    internal sealed class ValidationRules
    {
        public int MaxLength { get; set; } = 32;
        public string AllowedCharset { get; set; } = "A-Z0-9-";
        public bool RequireSeqSegment { get; set; } = true;

        public Dictionary<string, object> ToPayload()
        {
            return new Dictionary<string, object>
            {
                ["max_length"] = MaxLength,
                ["allowed_charset"] = AllowedCharset ?? "A-Z0-9-",
                ["require_seq_segment"] = RequireSeqSegment,
            };
        }

        public static ValidationRules FromDict(Dictionary<string, object> data)
        {
            return new ValidationRules
            {
                MaxLength = NumberingJson.GetInt(data, "max_length", 32),
                AllowedCharset = NumberingJson.GetString(data, "allowed_charset") ?? "A-Z0-9-",
                RequireSeqSegment = NumberingJson.GetBool(data, "require_seq_segment", true),
            };
        }
    }

    internal sealed class UserSettingsDefinition
    {
        public string DefaultSchemeId { get; set; }
        public Dictionary<string, string> DefaultContext { get; set; } = new Dictionary<string, string>();
        public Dictionary<string, string> PropertyMap { get; set; } = new Dictionary<string, string>();
        public string ApplyMode { get; set; } = "active_config";
        public bool ShowAdvanced { get; set; }

        public static UserSettingsDefinition FromDict(Dictionary<string, object> data)
        {
            var settings = new UserSettingsDefinition
            {
                DefaultSchemeId = NumberingJson.GetString(data, "default_scheme_id"),
                ApplyMode = NumberingJson.GetString(data, "apply_mode") ?? "active_config",
            };

            Dictionary<string, object> context = NumberingJson.GetDict(data, "default_context");
            if (context != null)
            {
                foreach (var pair in context)
                {
                    settings.DefaultContext[pair.Key] = pair.Value != null ? pair.Value.ToString() : string.Empty;
                }
            }

            Dictionary<string, object> map = NumberingJson.GetDict(data, "sw_property_map");
            if (map != null)
            {
                foreach (var pair in map)
                {
                    settings.PropertyMap[pair.Key] = pair.Value != null ? pair.Value.ToString() : string.Empty;
                }
            }

            Dictionary<string, object> prefs = NumberingJson.GetDict(data, "ui_preferences");
            settings.ShowAdvanced = prefs != null && NumberingJson.GetBool(prefs, "show_advanced", false);

            return settings;
        }

        public Dictionary<string, object> ToPayload()
        {
            var payload = new Dictionary<string, object>
            {
                ["default_scheme_id"] = DefaultSchemeId ?? string.Empty,
                ["default_context"] = DefaultContext ?? new Dictionary<string, string>(),
                ["sw_property_map"] = PropertyMap ?? new Dictionary<string, string>(),
                ["apply_mode"] = ApplyMode ?? "active_config",
                ["ui_preferences"] = new Dictionary<string, object>
                {
                    ["show_advanced"] = ShowAdvanced
                }
            };
            return payload;
        }
    }

    internal static class NumberingJson
    {
        public static string GetString(Dictionary<string, object> data, string key)
        {
            if (data == null || !data.ContainsKey(key) || data[key] == null)
            {
                return null;
            }
            return data[key].ToString();
        }

        public static int GetInt(Dictionary<string, object> data, string key, int fallback)
        {
            if (data == null || !data.ContainsKey(key) || data[key] == null)
            {
                return fallback;
            }
            int value;
            return int.TryParse(data[key].ToString(), out value) ? value : fallback;
        }

        public static int? GetNullableInt(Dictionary<string, object> data, string key)
        {
            if (data == null || !data.ContainsKey(key) || data[key] == null)
            {
                return null;
            }
            int value;
            return int.TryParse(data[key].ToString(), out value) ? (int?)value : null;
        }

        public static bool GetBool(Dictionary<string, object> data, string key, bool fallback)
        {
            if (data == null || !data.ContainsKey(key) || data[key] == null)
            {
                return fallback;
            }
            bool value;
            return bool.TryParse(data[key].ToString(), out value) ? value : fallback;
        }

        public static Dictionary<string, object> GetDict(Dictionary<string, object> data, string key)
        {
            if (data == null || !data.ContainsKey(key))
            {
                return null;
            }
            return AsDict(data[key]);
        }

        public static List<string> GetStringList(Dictionary<string, object> data, string key)
        {
            var list = new List<string>();
            if (data == null || !data.ContainsKey(key))
            {
                return list;
            }
            foreach (object item in AsList(data[key]))
            {
                if (item != null)
                {
                    list.Add(item.ToString());
                }
            }
            return list;
        }

        public static List<Dictionary<string, object>> GetDictList(Dictionary<string, object> data, string key)
        {
            var list = new List<Dictionary<string, object>>();
            if (data == null || !data.ContainsKey(key))
            {
                return list;
            }
            foreach (object item in AsList(data[key]))
            {
                Dictionary<string, object> dict = AsDict(item);
                if (dict != null)
                {
                    list.Add(dict);
                }
            }
            return list;
        }

        public static Dictionary<string, object> AsDict(object value)
        {
            return value as Dictionary<string, object>;
        }

        public static List<object> AsList(object value)
        {
            if (value == null)
            {
                return new List<object>();
            }
            if (value is object[] array)
            {
                return new List<object>(array);
            }
            if (value is ArrayList list)
            {
                var output = new List<object>();
                foreach (object item in list)
                {
                    output.Add(item);
                }
                return output;
            }
            if (value is List<object> objList)
            {
                return objList;
            }
            return new List<object>();
        }
    }
}
