using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class ActiveModelInfo
    {
        public ModelDoc2 Model { get; set; }
        public string ActiveConfiguration { get; set; }
        public string StartTitle { get; set; }
        public string StartConfiguration { get; set; }
        public bool StartedFromDrawing { get; set; }
    }

    internal static class SolidWorksDocumentHelper
    {
        public static bool TryGetActiveModel(ISldWorks app, out ActiveModelInfo info, out string error)
        {
            info = null;
            error = string.Empty;

            ModelDoc2 active = app.ActiveDoc as ModelDoc2;
            if (active == null)
            {
                error = "No active document.";
                return false;
            }

            string startTitle = active.GetTitle();
            string startConfig = GetActiveConfigName(active);

            if (active.GetType() == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc drawing = active as DrawingDoc;
                View first = drawing != null ? drawing.GetFirstView() as View : null;
                View modelView = first != null ? first.GetNextView() as View : null;
                ModelDoc2 refModel = modelView != null ? modelView.ReferencedDocument : null;
                string refConfig = modelView != null ? modelView.ReferencedConfiguration : string.Empty;

                if (refModel == null)
                {
                    error = "Drawing has no referenced model.";
                    return false;
                }

                app.ActivateDoc(refModel.GetTitle());
                info = new ActiveModelInfo
                {
                    Model = refModel,
                    ActiveConfiguration = refConfig,
                    StartTitle = startTitle,
                    StartConfiguration = startConfig,
                    StartedFromDrawing = true
                };
                return true;
            }

            info = new ActiveModelInfo
            {
                Model = active,
                ActiveConfiguration = startConfig,
                StartTitle = startTitle,
                StartConfiguration = startConfig,
                StartedFromDrawing = false
            };
            return true;
        }

        public static List<string> GetConfigurationNames(ModelDoc2 model)
        {
            var result = new List<string>();
            if (model == null)
            {
                return result;
            }

            object namesObj = model.GetConfigurationNames();
            string[] names = namesObj as string[];
            if (names != null)
            {
                result.AddRange(names);
                return result;
            }

            foreach (object obj in ComInteropUtil.EnumerateCom(namesObj))
            {
                if (obj != null)
                {
                    result.Add(obj.ToString());
                }
            }
            return result;
        }

        private static string GetActiveConfigName(ModelDoc2 model)
        {
            if (model == null)
            {
                return string.Empty;
            }
            Configuration conf = model.GetActiveConfiguration() as Configuration;
            return conf != null ? conf.Name : string.Empty;
        }
    }
}
