using System;
using System.Collections.Generic;
using System.IO;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    public class SolidWorksExportService
    {
        private readonly ISldWorks _swApp;

        public SolidWorksExportService(ISldWorks swApp)
        {
            _swApp = swApp;
        }

        public ModelDoc2? ActiveDocument => _swApp.IActiveDoc2;

        public (string? pn, string? rev) ReadPnRev(ModelDoc2? doc)
        {
            if (doc == null)
            {
                return (null, null);
            }

            var config = doc.IGetActiveConfiguration();
            var configMgr = config != null ? doc.Extension.get_CustomPropertyManager(config.Name) : null;
            var generalMgr = doc.Extension.get_CustomPropertyManager(string.Empty);

            return (ReadProperty(configMgr, "PN") ?? ReadProperty(generalMgr, "PN"),
                    ReadProperty(configMgr, "REV") ?? ReadProperty(generalMgr, "REV"));
        }

        public void ApplyReservedPn(ModelDoc2? doc, string pn, string? rev, bool renameDocument)
        {
            if (doc == null)
            {
                throw new InvalidOperationException("No hay documento activo en SolidWorks.");
            }

            var config = doc.IGetActiveConfiguration();
            if (config != null && !string.IsNullOrWhiteSpace(pn) && !pn.Equals(config.Name, StringComparison.OrdinalIgnoreCase))
            {
                try
                {
                    doc.Extension.RenameConfiguration(config.Name, pn);
                }
                catch
                {
                    // ignore rename failures; property updates still proceed
                }
            }

            var configMgr = config != null ? doc.Extension.get_CustomPropertyManager(config.Name) : null;
            var generalMgr = doc.Extension.get_CustomPropertyManager(string.Empty);

            SetProperty(configMgr, "PN", pn);
            SetProperty(generalMgr, "PN", pn);
            if (!string.IsNullOrWhiteSpace(rev))
            {
                SetProperty(configMgr, "REV", rev);
                SetProperty(generalMgr, "REV", rev);
            }

            if (renameDocument)
            {
                RenameDocumentFile(doc, pn);
            }
        }

        public bool Freeze(ModelDoc2? doc)
        {
            if (doc == null)
            {
                return false;
            }
            try
            {
                doc.SetReadOnlyState((int)swReadOnlyStates_e.swReadOnlyState_ReadOnly);
                doc.GraphicsRedraw2();
                return true;
            }
            catch
            {
                return false;
            }
        }

        public bool Unfreeze(ModelDoc2? doc)
        {
            if (doc == null)
            {
                return false;
            }
            try
            {
                doc.SetReadOnlyState((int)swReadOnlyStates_e.swReadOnlyState_NotReadOnly);
                doc.GraphicsRedraw2();
                return true;
            }
            catch
            {
                return false;
            }
        }

        public IReadOnlyList<(string Title, string Path, swDocumentTypes_e Type)> ListOpenDocuments()
        {
            var result = new List<(string, string, swDocumentTypes_e)>();
            var docs = _swApp.GetDocuments() as object[];
            if (docs == null)
            {
                return result;
            }

            foreach (var d in docs)
            {
                if (d is ModelDoc2 md)
                {
                    result.Add((md.GetTitle(), md.GetPathName() ?? string.Empty, (swDocumentTypes_e)md.GetType()));
                }
            }
            return result;
        }

        private static string? ReadProperty(CustomPropertyManager? mgr, string key)
        {
            if (mgr == null)
            {
                return null;
            }
            try
            {
                mgr.Get4(key, false, out var val, out _, out _);
                return string.IsNullOrWhiteSpace(val) ? null : val;
            }
            catch
            {
                return null;
            }
        }

        private static void SetProperty(CustomPropertyManager? mgr, string key, string value)
        {
            if (mgr == null)
            {
                return;
            }
            try
            {
                mgr.Set2(key, value);
            }
            catch
            {
                // ignore
            }
        }

        private void RenameDocumentFile(ModelDoc2 doc, string pn)
        {
            try
            {
                var path = doc.GetPathName();
                if (string.IsNullOrWhiteSpace(path))
                {
                    return;
                }

                var folder = Path.GetDirectoryName(path);
                var ext = Path.GetExtension(path);
                if (string.IsNullOrWhiteSpace(folder) || string.IsNullOrWhiteSpace(ext))
                {
                    return;
                }

                var target = Path.Combine(folder, pn + ext);
                if (string.Equals(path, target, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }

                int errors = 0;
                int warnings = 0;
                doc.Extension.SaveAs(target, (int)swSaveAsVersion_e.swSaveAsCurrentVersion, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
            }
            catch
            {
                // swallow rename issues to avoid breaking the workflow
            }
        }
    }
}
