using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class SolidWorksPropertyWriter
    {
        public static void ApplyNumbering(
            ModelDoc2 model,
            IEnumerable<string> configurationNames,
            bool includeDocumentProperties,
            string partNumber,
            string revision,
            string displayCode,
            string schemeId,
            string partNumberProperty,
            string revisionProperty,
            string displayCodeProperty)
        {
            if (model == null)
            {
                return;
            }

            string partProp = string.IsNullOrWhiteSpace(partNumberProperty) ? "PartNumber" : partNumberProperty;
            string revProp = string.IsNullOrWhiteSpace(revisionProperty) ? "Revision" : revisionProperty;
            string displayProp = string.IsNullOrWhiteSpace(displayCodeProperty) ? "DisplayCode" : displayCodeProperty;

            if (includeDocumentProperties)
            {
                SetCustomProperty(model, string.Empty, partProp, partNumber);
                SetCustomProperty(model, string.Empty, revProp, revision);
                SetCustomProperty(model, string.Empty, displayProp, displayCode);
                if (!string.IsNullOrWhiteSpace(schemeId))
                {
                    SetCustomProperty(model, string.Empty, "TinyMRP_SchemeId", schemeId);
                }
            }

            if (configurationNames == null)
            {
                return;
            }

            foreach (string configName in configurationNames)
            {
                if (string.IsNullOrWhiteSpace(configName))
                {
                    continue;
                }
                SetCustomProperty(model, configName, partProp, partNumber);
                SetCustomProperty(model, configName, revProp, revision);
                SetCustomProperty(model, configName, displayProp, displayCode);
                if (!string.IsNullOrWhiteSpace(schemeId))
                {
                    SetCustomProperty(model, configName, "TinyMRP_SchemeId", schemeId);
                }
            }
        }

        public static void SetCustomProperty(ModelDoc2 model, string configName, string propertyName, string value)
        {
            if (model == null || string.IsNullOrWhiteSpace(propertyName))
            {
                return;
            }

            string conf = configName ?? string.Empty;
            CustomPropertyManager manager = model.Extension.CustomPropertyManager[conf];
            int result = manager.Set2(propertyName, value ?? string.Empty);
            if (result != 0)
            {
                manager.Add3(
                    propertyName,
                    (int)swCustomInfoType_e.swCustomInfoText,
                    value ?? string.Empty,
                    (int)swCustomPropertyAddOption_e.swCustomPropertyDeleteAndAdd);
            }
        }
    }
}
