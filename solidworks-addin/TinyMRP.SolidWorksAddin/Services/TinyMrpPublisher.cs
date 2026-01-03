using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class TinyMrpPublisher
    {
        private sealed class ModelEntry
        {
            public ModelDoc2 Model;
            public string ConfigurationName;
        }

        private struct DrawingReference
        {
            public ModelDoc2 Model;
            public Configuration Configuration;
        }

        private static readonly Regex SanitizeRegex = new Regex("[^\\x28-\\x7F\\x20\\x21]+", RegexOptions.Compiled);

        private readonly ISldWorks _swApp;
        private readonly TinyMrpConfig _config;
        private volatile bool _cancelRequested;

        public TinyMrpPublisher(ISldWorks swApp, TinyMrpConfig config)
        {
            _swApp = swApp;
            _config = config;
        }

        public void ProcessFiles(PublishOptions options, Action<string> log, Action<int, int> progress)
        {
            PublishOptions effective = NormalizeOptions(options);
            if (effective == null)
            {
                return;
            }

            try
            {
                ResetCancel();
                TraverseModel(true, string.Empty, effective, log, null, progress);
                System.Windows.Forms.MessageBox.Show("File creation finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("File creation failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
        }

        public void ProcessBom(PublishOptions options, Action<string> log, Action<int, int> progress)
        {
            PublishOptions effective = NormalizeOptions(options);
            if (effective == null)
            {
                return;
            }

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                System.Windows.Forms.MessageBox.Show("No active document.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            if (swConf == null)
            {
                System.Windows.Forms.MessageBox.Show("No active configuration.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            ResetCancel();
            try
            {
                string pubFolder = EnsureTrailingSlash(effective.BomFolder);
                if (string.IsNullOrWhiteSpace(pubFolder))
                {
                    System.Windows.Forms.MessageBox.Show("BOM output folder is empty.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }

                Directory.CreateDirectory(pubFolder);
                string bomFolder = Path.Combine(pubFolder, "bom");
                Directory.CreateDirectory(bomFolder);

                string exportTag = Path.Combine(bomFolder, GetFileString(swModel, swConf.Name) + "_" +
                    DateTime.Now.ToString("yyyy_MM_dd_HH_mm_ss"));
                string flatFile = TraverseModel(false, exportTag, effective, log, progress, null);
                string bomFile = exportTag + "_TREEBOM.txt";

                string modelPath = swModel.GetPathName();
                if (string.IsNullOrWhiteSpace(modelPath))
                {
                    System.Windows.Forms.MessageBox.Show("Active document must be saved before exporting BOM.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }

                ThrowIfCancelled();

                string template = _swApp.GetUserPreferenceStringValue(
                    (int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly);
                ModelDoc2 assyDoc = _swApp.NewDocument(template, 0, 0, 0) as ModelDoc2;
                AssemblyDoc swAssembly = assyDoc as AssemblyDoc;
                if (assyDoc == null || swAssembly == null)
                {
                    System.Windows.Forms.MessageBox.Show("Failed to create temporary assembly.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
                    return;
                }

                try
                {
                    _swApp.ActivateDoc(assyDoc.GetTitle());
                    swAssembly.AddComponent5(modelPath, 0, string.Empty, false, string.Empty, 0, 0, 0);
                    ModelDoc2 assyModel = _swApp.ActiveDoc as ModelDoc2;
                    if (assyModel == null)
                    {
                        System.Windows.Forms.MessageBox.Show("Failed to activate temporary assembly.", "TinyMRP",
                            System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
                        return;
                    }

                    Configuration assyConfig = assyModel.GetActiveConfiguration() as Configuration;
                    if (assyConfig == null)
                    {
                        System.Windows.Forms.MessageBox.Show("Failed to read assembly configuration.", "TinyMRP",
                            System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
                        return;
                    }

                    SetUnitPreferences(swModel);
                    ThrowIfCancelled();

                    int bomX = 69;
                    int bomY = 69;
                    BomTableAnnotation bomTable = assyModel.Extension.InsertBomTable3(
                        _config.BomTemplatePath,
                        bomX,
                        bomY,
                        (int)swBomType_e.swBomType_Indented,
                        assyConfig.Name,
                        true,
                        (int)swNumberingType_e.swNumberingType_Detailed,
                        true);

                    if (bomTable != null)
                    {
                        ITableAnnotation tableAnn = (ITableAnnotation)bomTable;
                        tableAnn.SaveAsText(bomFile, "\t");
                    }
                    else
                    {
                        Log(log, "Failed to create BOM table.");
                    }

                    string zipPath = exportTag + ".zip";
                    string workFolder = exportTag;

                    Directory.CreateDirectory(workFolder);
                    MoveFileIfExists(bomFile, Path.Combine(workFolder, Path.GetFileName(bomFile)));
                    MoveFileIfExists(flatFile, Path.Combine(workFolder, Path.GetFileName(flatFile)));

                    if (File.Exists(zipPath))
                    {
                        File.Delete(zipPath);
                    }

                    ZipFile.CreateFromDirectory(workFolder, zipPath);
                    TryDeleteDirectory(workFolder);
                }
                finally
                {
                    if (assyDoc != null)
                    {
                        _swApp.CloseDoc(assyDoc.GetTitle());
                    }
                }

                System.Windows.Forms.MessageBox.Show("BOM file generation finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
        }

        public void NormalizeUnits(Action<string> log)
        {
            NormalizeUnits(log, null);
        }

        public void NormalizeUnits(Action<string> log, Action<int, int> progress)
        {
            ModelDoc2 rootModel = null;
            string rootTitle = string.Empty;
            HashSet<string> initialDocs = null;

            try
            {
                ResetCancel();
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs);
                UpdateProgress(progress, 0, entries.Count);

                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();
                    SetUnitPreferences(entry.Model);
                    if (!string.IsNullOrWhiteSpace(entry.Model.GetPathName()))
                    {
                        entry.Model.Save2(true);
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                    CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                }

                Log(log, "Units normalized.");
                System.Windows.Forms.MessageBox.Show("Units normalized.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("Failed to normalize units: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                if (!string.IsNullOrWhiteSpace(rootTitle))
                {
                    _swApp.ActivateDoc(rootTitle);
                }

                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
            }
        }

        public void FreezeDesign(bool freeze, Action<string> log)
        {
            FreezeDesign(freeze, log, null);
        }

        public void FreezeDesign(bool freeze, Action<string> log, Action<int, int> progress)
        {
            ModelDoc2 rootModel = null;
            string rootTitle = string.Empty;
            HashSet<string> initialDocs = null;

            try
            {
                ResetCancel();
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs);
                UpdateProgress(progress, 0, entries.Count);

                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();

                    int docType = entry.Model.GetType();
                    if (docType == (int)swDocumentTypes_e.swDocPART)
                    {
                        bool closeAfter = !ReferenceEquals(entry.Model, rootModel);
                        FreezePart(entry.Model, freeze, closeAfter);
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                    CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                }

                System.Windows.Forms.MessageBox.Show(freeze ? "Freeze finished." : "Unfreeze finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("Freeze failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                if (!string.IsNullOrWhiteSpace(rootTitle))
                {
                    _swApp.ActivateDoc(rootTitle);
                }

                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
            }
        }

        private void FreezeDesignInternal(ModelDoc2 swModel, bool freeze)
        {
            ModelView view = swModel.ActiveView as ModelView;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            if (swModel.FeatureManager != null)
            {
                swModel.FeatureManager.EnableFeatureTree = false;
            }

            int docType = swModel.GetType();
            if (docType == (int)swDocumentTypes_e.swDocPART)
            {
                FreezePart(swModel, freeze);
            }
            else if (docType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                AssemblyDoc assy = swModel as AssemblyDoc;
                if (assy != null)
                {
                    assy.ResolveAllLightWeightComponents(true);
                }
                FreezeTraverseModel(swModel, freeze);
            }
            else if (docType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                if (swDraw != null)
                {
                    View firstView = swDraw.GetFirstView() as View;
                    View modelView = firstView != null ? firstView.GetNextView() as View : null;
                    ModelDoc2 refModel = modelView != null ? modelView.ReferencedDocument : null;
                    if (refModel != null)
                    {
                        FreezeDesignInternal(refModel, freeze);
                    }
                }
            }

            if (swModel.FeatureManager != null)
            {
                swModel.FeatureManager.EnableFeatureTree = true;
            }

            if (view != null)
            {
                view.EnableGraphicsUpdate = true;
            }
        }

        private void FreezePart(ModelDoc2 model, bool freeze)
        {
            FreezePart(model, freeze, true);
        }

        private void FreezePart(ModelDoc2 model, bool freeze, bool closeAfter)
        {
            PartDoc part = model as PartDoc;
            if (part == null)
            {
                return;
            }

            _swApp.ActivateDoc(model.GetTitle());

            ModelView view = model.ActiveView as ModelView;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = false;
            }

            if (HasCutList(model))
            {
                model.Extension.SetUserPreferenceToggle(
                    (int)swUserPreferenceToggle_e.swWeldmentEnableAutomaticUpdate, 0, !freeze);
            }

            FeatureManager featMgr = model.FeatureManager;
            if (featMgr != null)
            {
                if (freeze)
                {
                    featMgr.EditFreeze2((int)swMoveFreezeBarTo_e.swMoveFreezeBarToEnd, string.Empty, true, true);
                }
                else
                {
                    featMgr.EditFreeze2((int)swMoveFreezeBarTo_e.swMoveFreezeBarToTop, string.Empty, true, true);
                    model.ForceRebuild3(true);
                }
            }

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = true;
            }

            if (view != null)
            {
                view.EnableGraphicsUpdate = true;
            }

            model.Save2(true);
            if (closeAfter)
            {
                _swApp.CloseDoc(model.GetTitle());
            }
        }

        private void FreezeTraverseModel(ModelDoc2 assemblyModel, bool freeze)
        {
            Configuration config = assemblyModel.GetActiveConfiguration() as Configuration;
            if (config == null)
            {
                return;
            }

            Component2 root = config.GetRootComponent() as Component2;
            if (root == null)
            {
                return;
            }

            object[] comps = root.GetChildren() as object[];
            if (comps == null)
            {
                return;
            }

            foreach (object obj in comps)
            {
                Component2 comp = obj as Component2;
                if (comp == null || comp.IsSuppressed())
                {
                    continue;
                }

                ModelDoc2 compModel = comp.GetModelDoc2() as ModelDoc2;
                if (compModel == null)
                {
                    continue;
                }

                FreezePart(compModel, freeze);
                FreezeTraverseModel(compModel, freeze);
            }
        }

        private bool HasCutList(ModelDoc2 model)
        {
            Feature feat = model.FirstFeature() as Feature;
            while (feat != null)
            {
                if (string.Equals(feat.GetTypeName(), "CutListFolder", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }

                feat = feat.GetNextFeature() as Feature;
            }

            return false;
        }

        private string TraverseModel(bool createFiles, string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress, Action<int, int> deliverablesProgress)
        {
            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            if (swConf == null)
            {
                throw new InvalidOperationException("No active configuration.");
            }

            int modelType = swModel.GetType();
            if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(swDraw, out reference))
                {
                    swModel = reference.Model;
                    swConf = reference.Configuration;
                    modelType = swModel.GetType();
                    _swApp.ActivateDoc(swModel.GetTitle());
                }
            }

            string pubFolder = EnsureTrailingSlash(options.BomFolder);
            if (string.IsNullOrWhiteSpace(pubFolder))
            {
                throw new InvalidOperationException("BOM folder is empty.");
            }

            string bomFolder = Path.Combine(pubFolder, "bom");
            Directory.CreateDirectory(bomFolder);

            string deliverablesFolder = EnsureTrailingSlash(options.DeliverablesFolder);
            if (string.IsNullOrWhiteSpace(deliverablesFolder))
            {
                throw new InvalidOperationException("Deliverables folder is empty.");
            }

            Directory.CreateDirectory(deliverablesFolder);
            EnsureMediaFolders(deliverablesFolder);

            ModelView view = swModel.ActiveView as ModelView;
            bool prevGraphics = view != null && view.EnableGraphicsUpdate;
            int prevBgAppearance = _swApp.GetUserPreferenceIntegerValue(
                (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance);
            int prevColorScheme = _swApp.GetUserPreferenceIntegerValue(
                (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme);
            int prevViewport = _swApp.GetUserPreferenceIntegerValue(
                (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground);

            ModelDoc2 rootModel = swModel;
            string rootTitle = swModel.GetTitle();
            HashSet<string> initialDocs = GetOpenDocumentIds();

            try
            {
                if (view != null)
                {
                    view.EnableGraphicsUpdate = false;
                }

                if (swModel.FeatureManager != null)
                {
                    swModel.FeatureManager.EnableFeatureTree = false;
                }

                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance, 0);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme,
                    (int)swSystemColorsCurrentColorScheme_e.swSystemColorsCurrentColorSchemeBlueHighlight);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground, 16777215);

                var entries = new List<ModelEntry>();
                var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                AddModelEntry(swModel, swConf.Name, entries, seen, false);

                if (modelType == (int)swDocumentTypes_e.swDocASSEMBLY)
                {
                    AssemblyDoc assy = swModel as AssemblyDoc;
                    if (assy != null)
                    {
                        assy.ResolveAllLightWeightComponents(true);
                    }
                    if (!options.TopLevelOnly)
                    {
                        Component2 root = swConf.GetRootComponent() as Component2;
                        TraverseComponents(root, entries, seen);
                    }
                }

                string outputFile;
                if (string.IsNullOrWhiteSpace(exportTag))
                {
                    outputFile = Path.Combine(bomFolder,
                        GetFileString(swModel, swConf.Name) + "_" +
                        DateTime.Now.ToString("yyyy_MM_dd_HH_mm_ss") + "_FLATBOM.txt");
                }
                else
                {
                    outputFile = exportTag + "_FLATBOM.txt";
                }

                UpdateProgress(flatBomProgress, 0, entries.Count);
                WriteFlatBom(outputFile, entries, log, flatBomProgress);
                ThrowIfCancelled();

                if (createFiles)
                {
                    UpdateProgress(deliverablesProgress, 0, entries.Count);
                    int processed = 0;
                    foreach (ModelEntry entry in entries)
                    {
                        ThrowIfCancelled();
                        ProcessDeliverables(entry, deliverablesFolder, options, log);
                        CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                        processed++;
                        UpdateProgress(deliverablesProgress, processed, entries.Count);
                    }
                }

                return outputFile;
            }
            finally
            {
                if (!string.IsNullOrWhiteSpace(rootTitle))
                {
                    _swApp.ActivateDoc(rootTitle);
                }

                if (swModel.FeatureManager != null)
                {
                    swModel.FeatureManager.EnableFeatureTree = true;
                }

                if (view != null)
                {
                    view.EnableGraphicsUpdate = prevGraphics;
                }

                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance, prevBgAppearance);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme, prevColorScheme);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground, prevViewport);

                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
            }
        }

        private List<ModelEntry> GetEntriesForActiveDoc(bool includeChildren, out ModelDoc2 rootModel,
            out string rootTitle, out HashSet<string> initialDocs)
        {
            ThrowIfCancelled();

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            if (swConf == null)
            {
                throw new InvalidOperationException("No active configuration.");
            }

            int modelType = swModel.GetType();
            if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(swDraw, out reference) && reference.Model != null)
                {
                    swModel = reference.Model;
                    swConf = reference.Configuration;
                    modelType = swModel.GetType();
                    _swApp.ActivateDoc(swModel.GetTitle());
                }
            }

            rootModel = swModel;
            rootTitle = swModel.GetTitle();
            initialDocs = GetOpenDocumentIds();

            var entries = new List<ModelEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            AddModelEntry(swModel, swConf.Name, entries, seen, false);

            if (includeChildren && modelType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                AssemblyDoc assy = swModel as AssemblyDoc;
                if (assy != null)
                {
                    assy.ResolveAllLightWeightComponents(true);
                }

                Component2 root = swConf.GetRootComponent() as Component2;
                TraverseComponents(root, entries, seen);
            }

            return entries;
        }

        private void AddModelEntry(ModelDoc2 model, string configName, List<ModelEntry> entries, HashSet<string> seen, bool prepend)
        {
            ThrowIfCancelled();
            string path = model.GetPathName();
            if (string.IsNullOrWhiteSpace(path))
            {
                path = model.GetTitle();
            }

            string key = path + configName + GetEvalProperty(model, configName, "revision");
            if (!seen.Add(key))
            {
                return;
            }

            var entry = new ModelEntry
            {
                Model = model,
                ConfigurationName = configName
            };

            if (prepend)
            {
                entries.Insert(0, entry);
            }
            else
            {
                entries.Add(entry);
            }
        }

        private void TraverseComponents(Component2 parent, List<ModelEntry> entries, HashSet<string> seen)
        {
            if (parent == null)
            {
                return;
            }

            object[] children = parent.GetChildren() as object[];
            if (children == null)
            {
                return;
            }

            foreach (object obj in children)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();
                Component2 child = obj as Component2;
                if (child == null)
                {
                    continue;
                }

                if (child.IsSuppressed() || child.ExcludeFromBOM)
                {
                    continue;
                }

                ModelDoc2 childModel = child.GetModelDoc2() as ModelDoc2;
                if (childModel == null)
                {
                    continue;
                }

                string confName = child.ReferencedConfiguration;
                AddModelEntry(childModel, confName, entries, seen, true);
                TraverseComponents(child, entries, seen);
            }
        }

        private void WriteFlatBom(string outputFile, List<ModelEntry> entries, Action<string> log,
            Action<int, int> progress)
        {
            using (var writer = new StreamWriter(outputFile, false, Encoding.UTF8))
            {
                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    try
                    {
                        writer.WriteLine(GetDocDict(entry.Model, entry.ConfigurationName));
                    }
                    catch (Exception ex)
                    {
                        Log(log, "Error building properties for model: " + ex.Message);
                        Configuration entryConf = entry.Model.GetConfigurationByName(entry.ConfigurationName) as Configuration;
                        string fallback = "{'partnumber':'" +
                                          SanitizeString(BomPartNumber(entryConf, entry.Model)) + "'}";
                        writer.WriteLine(fallback);
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                }
            }
        }

        private void ProcessDeliverables(ModelEntry entry, string deliverablesFolder, PublishOptions options, Action<string> log)
        {
            ModelDoc2 model = entry.Model;
            string confName = entry.ConfigurationName;
            ThrowIfCancelled();

            try
            {
                string fileString = GetFileString(model, confName);
                string modelPath = model.GetPathName();

                bool drawingExists = false;
                string drawingPath = string.Empty;
                if (!string.IsNullOrWhiteSpace(modelPath))
                {
                    Configuration modelConf = model.GetConfigurationByName(confName) as Configuration;
                    drawingPath = OnlyFolder(modelPath) +
                                  BomPartNumber(modelConf, model) + ".SLDDRW";
                    drawingExists = File.Exists(drawingPath);
                }

                bool createPng = options.ExportPngModel &&
                                 ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + ".png"),
                                     options.OverwriteFiles);

                bool createStep = (options.ExportStep ||
                                   HasProcess(model, confName, "FOLDING") ||
                                   HasProcess(model, confName, "MACHINE") ||
                                   HasProcess(model, confName, "3D Laser")) &&
                                  ShouldExport(Path.Combine(deliverablesFolder, "step", fileString + ".step"),
                                      options.OverwriteFiles);

                bool create3mf = options.Export3mf &&
                                 ShouldExport(Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf"),
                                     options.OverwriteFiles);

                bool createEdr = options.ExportEdrawing &&
                                 ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString +
                                     (model.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt")),
                                     options.OverwriteFiles);

                if (createPng || createStep || createEdr || create3mf)
                {
                    ModelPublish(model, confName, fileString, deliverablesFolder, createPng, createStep, createEdr, create3mf);
                }

                if (drawingExists)
                {
                    bool createPdf = options.ExportPdf &&
                                     ShouldExport(Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf"),
                                         options.OverwriteFiles);

                    bool createPngD = options.ExportPngDrawing &&
                                      ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png"),
                                          options.OverwriteFiles);

                    bool createEdrD = options.ExportEdrawingDrawing &&
                                      ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString + ".edrw"),
                                          options.OverwriteFiles);

                    if (createPdf || createPngD || createEdrD)
                    {
                        DwgPublish(model, fileString, deliverablesFolder, createPdf, createPngD, createEdrD);
                    }
                }
            }
            catch (Exception ex)
            {
                Log(log, "Deliverables error: " + ex.Message);
            }
        }

        private void EnsureMediaFolders(string deliverablesFolder)
        {
            string[] folders =
            {
                "png",
                "step",
                "pdf",
                "dxf",
                "edr",
                "3mf",
                "bom",
                Path.Combine("temp", "upload")
            };

            foreach (string folder in folders)
            {
                Directory.CreateDirectory(Path.Combine(deliverablesFolder, folder));
            }
        }

        private bool ShouldExport(string path, bool overwrite)
        {
            return overwrite || !File.Exists(path);
        }

        private void ModelPublish(ModelDoc2 model, string confName, string fileString, string deliverablesFolder,
            bool png, bool step, bool edr, bool threeMf)
        {
            _swApp.ActivateDoc(model.GetTitle());
            model.ShowConfiguration(confName);

            ModelView view = model.GetFirstModelView() as ModelView;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            model.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swViewDisplayHideAllTypes, true);
            model.ForceRebuild3(true);

            int errors = 0;
            int warnings = 0;

            if (threeMf)
            {
                string path = Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf");
                model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
            }

            if (step)
            {
                string path = Path.Combine(deliverablesFolder, "step", fileString + ".step");
                model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
            }

            if (edr)
            {
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                    (int)swEdrawingSaveAsOption_e.swEdrawingSaveActive);

                string ext = model.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt";
                string path = Path.Combine(deliverablesFolder, "edr", fileString + ext);
                model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
            }

            if (png)
            {
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swTiffScreenOrPrintCapture, 1);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swTiffPrintDPI, 150);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swTiffPrintPaperSize,
                    (int)swDwgPaperSizes_e.swDwgPapersUserDefined);
                _swApp.SetUserPreferenceDoubleValue(
                    (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperWidth, 0.297);
                _swApp.SetUserPreferenceDoubleValue(
                    (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperHeight, 0.21);

                model.ShowNamedView2("Isometric", 7);
                model.ViewZoomtofit2();

                if (view != null)
                {
                    view.EnableGraphicsUpdate = true;
                }

                string path = Path.Combine(deliverablesFolder, "png", fileString + ".png");
                model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
            }
        }

        private void DwgPublish(ModelDoc2 model, string fileString, string deliverablesFolder,
            bool pdf, bool png, bool edr)
        {
            Configuration conf = model.GetActiveConfiguration() as Configuration;
            if (conf == null)
            {
                return;
            }

            string modelPath = model.GetPathName();
            if (string.IsNullOrWhiteSpace(modelPath))
            {
                return;
            }

            string drawingPath = OnlyFolder(modelPath) + BomPartNumber(conf, model) + ".SLDDRW";
            if (!File.Exists(drawingPath))
            {
                return;
            }

            string pdfPath = Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf");
            string dxfPath = Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf");
            string pngPath = Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png");
            string edrPath = Path.Combine(deliverablesFolder, "edr", fileString + ".edrw");

            DocumentSpecification spec = _swApp.GetOpenDocSpec(drawingPath) as DocumentSpecification;
            if (spec == null)
            {
                return;
            }
            spec.DocumentType = (int)swDocumentTypes_e.swDocDRAWING;
            spec.ReadOnly = true;
            spec.Silent = true;

            ModelDoc2 drawDoc = _swApp.OpenDoc7(spec) as ModelDoc2;
            if (drawDoc == null)
            {
                return;
            }

            try
            {
                _swApp.ActivateDoc(drawDoc.GetTitle());

                DrawingDoc drawing = drawDoc as DrawingDoc;
                if (drawing == null)
                {
                    return;
                }

                object sheetNamesObj = drawing.GetSheetNames();
                string[] sheetNames = ToStringArray(sheetNamesObj);
                if (sheetNames == null || sheetNames.Length == 0)
                {
                    return;
                }

                bool dxfNeeded = false;
                string dxfSheetName = string.Empty;
                Sheet dxfSheet = null;

                for (int i = 0; i < sheetNames.Length; i++)
                {
                    Sheet sheet = drawing.get_Sheet(sheetNames[i]);
                    drawDoc.ForceRebuild3(true);

                    string lower = sheetNames[i].ToLowerInvariant();
                    if (lower == "flatpattern" || lower == "dxf" || lower == "dxf sheet")
                    {
                        dxfNeeded = true;
                        dxfSheetName = sheetNames[i];
                        dxfSheet = sheet;
                    }
                }

                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swDxfMultiSheetOption,
                    (int)swDxfMultisheet_e.swDxfActiveSheetOnly);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swDxfOutputNoScale, 1);

                int errors = 0;
                int warnings = 0;

                if (pdf)
                {
                    ExportPdfData exportData = _swApp.GetExportFileData(
                        (int)swExportDataFileType_e.swExportPdfData) as ExportPdfData;
                    if (exportData != null)
                    {
                        exportData.SetSheets((int)swExportDataSheetsToExport_e.swExportData_ExportSpecifiedSheets,
                            sheetNames);
                        drawDoc.Extension.SaveAs(pdfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, exportData, ref errors, ref warnings);
                    }
                }

                if (edr)
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                        (int)swEdrawingSaveAsOption_e.swEdrawingSaveAll);
                    drawDoc.Extension.SaveAs(edrPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                }

                if (png)
                {
                    drawing.ActivateSheet(sheetNames[0]);
                    drawing.ViewFullPage();

                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swTiffScreenOrPrintCapture, 1);
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swTiffPrintDPI, 150);
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swTiffPrintPaperSize,
                        (int)swDwgPaperSizes_e.swDwgPapersUserDefined);
                    _swApp.SetUserPreferenceDoubleValue(
                        (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperWidth, 0.297);
                    _swApp.SetUserPreferenceDoubleValue(
                        (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperHeight, 0.21);

                    drawDoc.Extension.SaveAs(pngPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                }

                if (dxfNeeded && dxfSheet != null)
                {
                    drawing.ActivateSheet(dxfSheetName);
                    ReplaceSheetFormat(drawing, dxfSheet, _config.BlankTemplatePath);
                    drawDoc.SaveAs4(dxfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref errors, ref warnings);
                }
                else
                {
                    View flatView = drawing.GetFirstView() as View;
                    View flatPatternView = null;
                    while (flatView != null)
                    {
                        if (string.Equals(flatView.GetName2(), "FLATPATTERN", StringComparison.OrdinalIgnoreCase))
                        {
                            flatPatternView = flatView;
                            break;
                        }

                        flatView = flatView.GetNextView() as View;
                    }

                    if (flatPatternView != null)
                    {
                        ExportFlatPatternView(drawDoc, flatPatternView, dxfPath);
                    }
                }
            }
            finally
            {
                _swApp.CloseDoc(drawDoc.GetTitle());
            }
        }

        private void ReplaceSheetFormat(DrawingDoc draw, Sheet sheet, string targetSheetFormatFile)
        {
            object propsObj = sheet.GetProperties();
            object[] props = propsObj as object[];
            if (props == null || props.Length < 7)
            {
                return;
            }

            int paperSize = Convert.ToInt32(props[0]);
            int templateType = Convert.ToInt32(props[1]);
            double scale1 = Convert.ToDouble(props[2]);
            double scale2 = Convert.ToDouble(props[3]);
            bool firstAngle = Convert.ToBoolean(props[4]);
            double width = Convert.ToDouble(props[5]);
            double height = Convert.ToDouble(props[6]);
            string customView = sheet.CustomPropertyView;

            bool result = draw.SetupSheet5(sheet.GetName(), paperSize, templateType, scale1, scale2, firstAngle,
                targetSheetFormatFile, width, height, customView, _config.RemoveModifiedNotes);

            if (!result)
            {
                throw new InvalidOperationException("Failed to set sheet format.");
            }
        }

        private void ExportFlatPatternView(ModelDoc2 model, View view, string dxfFilePath)
        {
            object[] views = { view };
            int selected = model.Extension.MultiSelect2(views, false, null);
            if (selected == 1)
            {
                model.EditCopy();
                ModelDoc2 viewModel = PasteViewInNewDocument();
                int errors = 0;
                int warnings = 0;
                bool result = viewModel.Extension.SaveAs(dxfFilePath,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                _swApp.CloseDoc(viewModel.GetTitle());

                if (!result)
                {
                    throw new InvalidOperationException("Failed to export " + view.Name);
                }
            }
            else
            {
                throw new InvalidOperationException("Failed to select " + view.Name);
            }
        }

        private ModelDoc2 PasteViewInNewDocument()
        {
            ModelDoc2 drawDoc = _swApp.NewDocument(_config.BlankTemplatePath,
                (int)swDwgPaperSizes_e.swDwgPapersUserDefined, 0.1, 0.1) as ModelDoc2;

            if (drawDoc == null)
            {
                throw new InvalidOperationException("Failed to create new drawing document.");
            }

            drawDoc.Paste();

            DrawingDoc drawing = drawDoc as DrawingDoc;
            if (drawing == null)
            {
                return drawDoc;
            }

            Sheet sheet = drawing.GetCurrentSheet() as Sheet;
            if (sheet == null)
            {
                return drawDoc;
            }
            object[] viewsObj = sheet.GetViews() as object[];
            View view = viewsObj != null && viewsObj.Length > 0 ? viewsObj[0] as View : null;
            if (view == null)
            {
                return drawDoc;
            }

            double[] ratio = { 1.0, 1.0 };
            view.ScaleRatio = ratio;
            sheet.SetScale(1, 1, false, false);

            drawDoc.ForceRebuild3(true);
            RemoveDimensions(drawDoc, view);
            RemoveTables(drawDoc, view);
            FitSheetToView(sheet, view);

            return drawDoc;
        }

        private void RemoveDimensions(ModelDoc2 model, View view)
        {
            object annotationsObj = view.GetAnnotations();
            object[] annotations = annotationsObj as object[];
            if (annotations == null || annotations.Length == 0)
            {
                return;
            }

            var toDelete = new List<Annotation>();
            foreach (object obj in annotations)
            {
                Annotation ann = obj as Annotation;
                if (ann != null)
                {
                    toDelete.Add(ann);
                }
            }

            if (toDelete.Count == 0)
            {
                return;
            }

            int selected = model.Extension.MultiSelect2(toDelete.ToArray(), false, null);
            if (selected == toDelete.Count)
            {
                model.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
            }
        }

        private void RemoveTables(ModelDoc2 model, View view)
        {
            DrawingDoc drawing = model as DrawingDoc;
            if (drawing == null)
            {
                return;
            }

            object sheetsObj = drawing.GetViews();
            object[] sheets = sheetsObj as object[];
            if (sheets == null || sheets.Length == 0)
            {
                return;
            }

            object[] firstSheetViews = sheets[0] as object[];
            if (firstSheetViews == null || firstSheetViews.Length == 0)
            {
                return;
            }

            View sheetView = firstSheetViews[0] as View;
            if (sheetView == null)
            {
                return;
            }

            object tablesObj = sheetView.GetTableAnnotations();
            object[] tables = tablesObj as object[];
            if (tables == null || tables.Length == 0)
            {
                return;
            }

            int selected = model.Extension.MultiSelect2(tables, false, null);
            if (selected == tables.Length)
            {
                model.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
            }
        }

        private void FitSheetToView(Sheet sheet, View view)
        {
            double[] outline = view.GetOutline() as double[];
            if (outline == null || outline.Length < 4)
            {
                return;
            }

            double width = outline[2] - outline[0];
            double height = outline[3] - outline[1];
            sheet.SetSize((int)swDwgPaperSizes_e.swDwgPapersUserDefined, width, height);

            double[] position = view.Position as double[];
            if (position == null || position.Length < 2)
            {
                return;
            }

            position[0] = position[0] - outline[0];
            position[1] = position[1] - outline[1];
            view.Position = position;
        }

        private bool TryGetDrawingReference(DrawingDoc draw, out DrawingReference reference)
        {
            reference = new DrawingReference();
            if (draw == null)
            {
                return false;
            }

            string[] sheetNames = ToStringArray(draw.GetSheetNames());
            if (sheetNames == null || sheetNames.Length == 0)
            {
                return false;
            }

            Sheet sheet = draw.get_Sheet(sheetNames[0]);
            if (sheet == null)
            {
                return false;
            }

            draw.ActivateSheet(sheetNames[0]);

            string viewName = sheet.CustomPropertyView;
            View[] views = GetSheetViews(draw, sheet);
            if (views == null || views.Length == 0)
            {
                return false;
            }

            if (string.Equals(viewName, "Default", StringComparison.OrdinalIgnoreCase))
            {
                viewName = views[0].Name;
            }

            foreach (View view in views)
            {
                if (string.Equals(view.Name, viewName, StringComparison.OrdinalIgnoreCase))
                {
                    ModelDoc2 model = view.ReferencedDocument;
                    string confName = view.ReferencedConfiguration;
                    if (model == null)
                    {
                        return false;
                    }

                    model.ShowConfiguration(confName);
                    Configuration conf = model.GetConfigurationByName(confName) as Configuration;
                    reference = new DrawingReference { Model = model, Configuration = conf };
                    return true;
                }
            }

            return false;
        }

        private View[] GetSheetViews(DrawingDoc draw, Sheet sheet)
        {
            object viewsObj = draw.GetViews();
            object[] sheets = viewsObj as object[];
            if (sheets == null)
            {
                return new View[0];
            }

            foreach (object sheetViewsObj in sheets)
            {
                object[] views = sheetViewsObj as object[];
                if (views == null || views.Length == 0)
                {
                    continue;
                }

                View sheetView = views[0] as View;
                if (sheetView != null &&
                    string.Equals(sheetView.Name, sheet.GetName(), StringComparison.OrdinalIgnoreCase))
                {
                    if (views.Length <= 1)
                    {
                        return new View[0];
                    }

                    var result = new View[views.Length - 1];
                    for (int i = 1; i < views.Length; i++)
                    {
                        result[i - 1] = views[i] as View;
                    }

                    return result;
                }
            }

            return new View[0];
        }

        private string GetFileString(ModelDoc2 model, string configName)
        {
            string tempRev = GetEvalProperty(model, configName, "revision");
            Configuration config = model.GetConfigurationByName(configName) as Configuration;
            string fileString = BomPartNumber(config, model) + "_REV_" + tempRev;
            return fileString.ToUpperInvariant();
        }

        private string BomPartNumber(Configuration config, ModelDoc2 document)
        {
            if (config == null)
            {
                return string.Empty;
            }

            string partNumber = string.Empty;
            switch ((swBOMPartNumberSource_e)config.BOMPartNoSource)
            {
                case swBOMPartNumberSource_e.swBOMPartNumber_ConfigurationName:
                    partNumber = config.Name;
                    break;
                case swBOMPartNumberSource_e.swBOMPartNumber_DocumentName:
                    string title = document.GetTitle();
                    partNumber = Path.GetFileNameWithoutExtension(title);
                    break;
                case swBOMPartNumberSource_e.swBOMPartNumber_UserSpecified:
                    partNumber = config.AlternateName;
                    break;
                case swBOMPartNumberSource_e.swBOMPartNumber_ParentName:
                    Configuration parent = config.GetParent() as Configuration;
                    if (parent != null && parent.BOMPartNoSource == (int)swBOMPartNumberSource_e.swBOMPartNumber_ParentName)
                    {
                        partNumber = BomPartNumber(parent, document);
                    }
                    else if (parent != null)
                    {
                        partNumber = parent.Name;
                    }
                    break;
            }

            if (string.Equals(partNumber, "allocate", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(partNumber, "default", StringComparison.OrdinalIgnoreCase))
            {
                string baseName = OnlyFile(document.GetPathName());
                if (string.IsNullOrWhiteSpace(baseName))
                {
                    baseName = document.GetTitle();
                }

                partNumber = SanitizeFileName("FIX_" + baseName + "_" + config.Name);
                partNumber = ReplaceNonAlphaNumeric(partNumber);

                config.BOMPartNoSource = (int)swBOMPartNumberSource_e.swBOMPartNumber_UserSpecified;
                config.AlternateName = partNumber;
                config.UseAlternateNameInBOM = true;
                config.AlternateName = partNumber;
            }

            return partNumber;
        }

        private string ReplaceNonAlphaNumeric(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return string.Empty;
            }

            var result = new StringBuilder(input.Length);
            foreach (char c in input)
            {
                if (char.IsLetterOrDigit(c))
                {
                    result.Append(c);
                }
                else
                {
                    result.Append('_');
                }
            }

            return result.ToString();
        }

        private string SanitizeFileName(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return string.Empty;
            }

            string invalid = ",\\/:*?\"<>| ";
            foreach (char c in invalid)
            {
                string replacement = c == ' ' ? "_" : string.Empty;
                input = input.Replace(c.ToString(), replacement);
            }

            return input;
        }

        private string GetDocDict(ModelDoc2 model, string confName)
        {
            Configuration modelConf = model.GetConfigurationByName(confName) as Configuration;
            string[] minProperties =
            {
                "approved", "author", "checkedby", "category", "oem_data_sheet", "item_no", "description",
                "drawndate", "finish", "oem_internet", "mass", "material", "oem_supplier", "process", "process2",
                "process3", "revision", "spare_part", "distributor", "oem_part_number", "spare_part", "supplier",
                "supplier_partnumber", "asset", "thickness", "treatment", "colour", "design_notes", "comments",
                "classified", "secondprocess", "thirdprocess", "datasheet"
            };

            var json = new StringBuilder();
            json.Append("{");
            json.Append("'partnumber':'")
                .Append(SanitizeString(BomPartNumber(modelConf, model)))
                .Append("',");
            json.Append("'sw_configuration':'")
                .Append(SanitizeString(confName))
                .Append("',");

            for (int i = 0; i < minProperties.Length; i++)
            {
                string prop = minProperties[i];
                string value = GetEvalProperty(model, confName, prop);
                if (string.IsNullOrEmpty(value) &&
                    !string.Equals(prop, "partnumber", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(prop, "revision", StringComparison.OrdinalIgnoreCase))
                {
                    value = GetEvalProperty(model, string.Empty, prop);
                }

                json.Append("'").Append(prop).Append("':'")
                    .Append(SanitizeString((value ?? string.Empty).Replace("\\", "/")))
                    .Append("',");
            }

            json.Append("'path':'")
                .Append((model.GetPathName() ?? string.Empty).Replace("\\", "/"))
                .Append("',");
            json.Append("'file':'")
                .Append(OnlyFile(model.GetPathName()))
                .Append("',");
            json.Append("'folder':'")
                .Append(OnlyFolder(model.GetPathName()).Replace("\\", "/"))
                .Append("'");

            string[] configProps = GetCustomPropertyNames(model, confName);
            foreach (string prop in configProps)
            {
                if (string.IsNullOrWhiteSpace(prop))
                {
                    continue;
                }

                if (ContainsProperty(json, prop) ||
                    string.Equals(prop, "partnumber", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string value = GetEvalProperty(model, confName, prop);
                json.Append(",'").Append(prop).Append("':'")
                    .Append(SanitizeString((value ?? string.Empty).Replace("\\", "/")))
                    .Append("'");
            }

            string[] partProps = GetCustomPropertyNames(model, string.Empty);
            foreach (string prop in partProps)
            {
                if (string.IsNullOrWhiteSpace(prop))
                {
                    continue;
                }

                if (ContainsProperty(json, prop) ||
                    string.Equals(prop, "partnumber", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string value = GetEvalProperty(model, string.Empty, prop);
                json.Append(",'").Append(prop).Append("':'")
                    .Append(SanitizeString((value ?? string.Empty).Replace("\\", "/")))
                    .Append("'");
            }

            json.Append("}");
            return json.ToString();
        }

        private string[] GetCustomPropertyNames(ModelDoc2 model, string confName)
        {
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[confName];
            object namesObj = cpm.GetNames();
            return ToStringArray(namesObj) ?? new string[0];
        }

        private static string[] ToStringArray(object values)
        {
            string[] strings = values as string[];
            if (strings != null)
            {
                return strings;
            }

            object[] objs = values as object[];
            if (objs == null)
            {
                return null;
            }

            var result = new string[objs.Length];
            for (int i = 0; i < objs.Length; i++)
            {
                result[i] = objs[i] != null ? objs[i].ToString() : string.Empty;
            }

            return result;
        }

        private bool ContainsProperty(StringBuilder json, string prop)
        {
            if (string.IsNullOrWhiteSpace(prop))
            {
                return false;
            }

            return json.ToString().IndexOf("'" + prop + "':", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private string GetEvalProperty(ModelDoc2 model, string confName, string property)
        {
            if (model == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrEmpty(confName))
            {
                model.ShowConfiguration(confName);
            }

            string valOut;
            string resolved;
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[confName];
            cpm.Get2(property, out valOut, out resolved);

            if (string.Equals(property, "revision", StringComparison.OrdinalIgnoreCase) &&
                string.IsNullOrEmpty(resolved))
            {
                cpm = model.Extension.CustomPropertyManager[string.Empty];
                cpm.Get2(property, out valOut, out resolved);
            }

            return resolved ?? string.Empty;
        }

        private bool HasProcess(ModelDoc2 model, string confName, string process)
        {
            if (string.IsNullOrWhiteSpace(process))
            {
                return false;
            }

            return ContainsIgnoreCase(GetEvalProperty(model, confName, "process"), process) ||
                   ContainsIgnoreCase(GetEvalProperty(model, confName, "process2"), process) ||
                   ContainsIgnoreCase(GetEvalProperty(model, confName, "process3"), process);
        }

        private bool ContainsIgnoreCase(string source, string value)
        {
            if (string.IsNullOrEmpty(source) || string.IsNullOrEmpty(value))
            {
                return false;
            }

            return source.IndexOf(value, StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private string SanitizeString(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return string.Empty;
            }

            return SanitizeRegex.Replace(input, string.Empty);
        }

        private string OnlyFile(string path)
        {
            return string.IsNullOrWhiteSpace(path) ? string.Empty : Path.GetFileName(path);
        }

        private string OnlyFolder(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            string folder = Path.GetDirectoryName(path);
            if (string.IsNullOrWhiteSpace(folder))
            {
                return string.Empty;
            }

            return EnsureTrailingSlash(folder);
        }

        private string EnsureTrailingSlash(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            if (path.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal))
            {
                return path;
            }

            return path + Path.DirectorySeparatorChar;
        }

        private void SetUnitPreferences(ModelDoc2 model)
        {
            ModelDocExtension ext = model.Extension;
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0,
                (int)swLengthUnit_e.swMM);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsLinearDecimalPlaces, 0, 1);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsDualLinear, 0,
                (int)swLengthUnit_e.swMM);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsDualLinearDecimalPlaces, 0, 4);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsAngular, 0,
                (int)swAngleUnit_e.swDEGREES);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsAngularDecimalPlaces, 0, 1);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropLength, 0,
                (int)swLengthUnit_e.swMM);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropDecimalPlaces, 0, 1);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropMass, 0,
                (int)swUnitsMassPropMass_e.swUnitsMassPropMass_Kilograms);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropVolume, 0,
                (int)swUnitsMassPropVolume_e.swUnitsMassPropVolume_Liters);
        }

        private PublishOptions NormalizeOptions(PublishOptions options)
        {
            if (options == null)
            {
                options = new PublishOptions();
            }

            if (string.IsNullOrWhiteSpace(options.DeliverablesFolder))
            {
                options.DeliverablesFolder = _config.DeliverablesFolder;
            }

            if (string.IsNullOrWhiteSpace(options.BomFolder))
            {
                options.BomFolder = _config.BomFolder;
            }

            return options;
        }

        private void Log(Action<string> log, string message)
        {
            if (log != null)
            {
                log(message);
            }
        }

        private void UpdateProgress(Action<int, int> progress, int current, int total)
        {
            if (progress != null)
            {
                progress(current, total);
            }
        }

        public void RequestCancel()
        {
            _cancelRequested = true;
        }

        private void ResetCancel()
        {
            _cancelRequested = false;
        }

        private void ThrowIfCancelled()
        {
            if (_cancelRequested)
            {
                throw new OperationCanceledException();
            }
        }

        private void MoveFileIfExists(string source, string dest)
        {
            if (string.IsNullOrWhiteSpace(source) || !File.Exists(source))
            {
                return;
            }

            if (File.Exists(dest))
            {
                File.Delete(dest);
            }

            File.Move(source, dest);
        }

        private void TryDeleteDirectory(string path)
        {
            try
            {
                if (Directory.Exists(path))
                {
                    Directory.Delete(path, true);
                }
            }
            catch
            {
                // ignore cleanup errors
            }
        }

        private void CloseNonRootDocs(HashSet<string> initialDocs, ModelDoc2 rootModel, string rootTitle)
        {
            if (rootModel == null)
            {
                return;
            }
            if (initialDocs == null)
            {
                return;
            }

            object docsObj = _swApp.GetDocuments();
            object[] docs = docsObj as object[];
            if (docs == null || docs.Length == 0)
            {
                return;
            }

            foreach (object obj in docs)
            {
                ModelDoc2 doc = obj as ModelDoc2;
                if (doc == null)
                {
                    continue;
                }

                if (ReferenceEquals(doc, rootModel))
                {
                    continue;
                }

                string title = doc.GetTitle();
                if (!string.IsNullOrWhiteSpace(rootTitle) &&
                    string.Equals(title, rootTitle, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string id = GetDocumentId(doc);
                if (!string.IsNullOrWhiteSpace(id) && initialDocs.Contains(id))
                {
                    continue;
                }

                try
                {
                    if (!string.IsNullOrWhiteSpace(title))
                    {
                        _swApp.CloseDoc(title);
                    }
                }
                catch
                {
                    // ignore close errors
                }
            }
        }

        private HashSet<string> GetOpenDocumentIds()
        {
            var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            object docsObj = _swApp.GetDocuments();
            object[] docs = docsObj as object[];
            if (docs == null)
            {
                return ids;
            }

            foreach (object obj in docs)
            {
                ModelDoc2 doc = obj as ModelDoc2;
                if (doc == null)
                {
                    continue;
                }

                string id = GetDocumentId(doc);
                if (!string.IsNullOrWhiteSpace(id))
                {
                    ids.Add(id);
                }
            }

            return ids;
        }

        private string GetDocumentId(ModelDoc2 doc)
        {
            if (doc == null)
            {
                return string.Empty;
            }

            string path = doc.GetPathName();
            if (!string.IsNullOrWhiteSpace(path))
            {
                return path;
            }

            return doc.GetTitle();
        }
    }
}
