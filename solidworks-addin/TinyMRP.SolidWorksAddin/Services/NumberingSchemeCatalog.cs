using System.Collections.Generic;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class NumberingSchemeCatalog
    {
        internal const string NewSchemePlaceholderName = "(new scheme)";

        public static NumberingSchemeDefinition CreateBasicScheme(string name = "")
        {
            var scheme = new NumberingSchemeDefinition
            {
                Name = name ?? string.Empty,
                IsActive = true
            };

            ApplyBasicTemplate(scheme, "PART", 6, true);
            return scheme;
        }

        public static void ApplyBasicTemplate(NumberingSchemeDefinition scheme, string literalValue, int padding, bool includeLiteral)
        {
            if (scheme == null)
            {
                return;
            }

            int normalizedPadding = padding > 0 ? padding : 6;
            scheme.IsActive = true;
            scheme.Separator = "-";
            scheme.ScopeMode = "global";
            scheme.ScopeKeys = new List<string>();
            scheme.Seq = new SequenceSettings
            {
                Padding = normalizedPadding,
                Base = 10,
                StartAt = 1,
                ResetPolicy = "never"
            };
            scheme.Revision = new RevisionSettings
            {
                Policy = "alpha",
                Start = "A"
            };
            scheme.ValidationRules = new ValidationRules
            {
                MaxLength = 32,
                AllowedCharset = "A-Z0-9-",
                RequireSeqSegment = true
            };

            var segments = new List<NumberingSegmentDefinition>();
            if (includeLiteral)
            {
                segments.Add(new NumberingSegmentDefinition
                {
                    Kind = "literal",
                    Value = literalValue ?? string.Empty
                });
            }
            segments.Add(new NumberingSegmentDefinition
            {
                Kind = "seq",
                Padding = normalizedPadding,
                Base = 10,
                StartAt = 1,
                AutoCounter = true
            });
            scheme.PatternSegments = segments;
        }

        public static List<NumberingSchemeDefinition> GetSelectableSchemes(IEnumerable<NumberingSchemeDefinition> schemes)
        {
            var output = new List<NumberingSchemeDefinition>();
            if (schemes == null)
            {
                return output;
            }

            foreach (NumberingSchemeDefinition scheme in schemes)
            {
                if (scheme == null || !scheme.IsActive)
                {
                    continue;
                }

                output.Add(scheme);
            }

            return output;
        }
    }
}
