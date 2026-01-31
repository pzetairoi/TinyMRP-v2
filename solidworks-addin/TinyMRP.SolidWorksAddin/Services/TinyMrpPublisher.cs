using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Globalization;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class TinyMrpPublisher
    {
        // Flip these to true when diagnosing hide-features issues.
        private static readonly bool EnableHideDebugLog = false;
        private static readonly bool EnableHideStatusLog = false;
        private sealed class ModelEntry
        {
            public ModelDoc2 Model;
            public string ConfigurationName;
        }

        private sealed class BatchEntry
        {
            public string ModelPath;
            public string ModelTitle;
            public string ConfigurationName;
            public bool IsRoot;
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
                HashSet<string> uploadPackBases;
                string flatFile = TraverseModel(true, string.Empty, effective, log, null, progress, out uploadPackBases);
                if (effective.CreateUploadPack)
                {
                    try
                    {
                        CreateUploadPack(flatFile, uploadPackBases, effective, log);
                    }
                    catch (Exception ex)
                    {
                        Log(log, "Upload pack failed: " + ex.Message);
                    }
                }
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

            string startTitle = swModel.GetTitle();
            HashSet<string> initialDocs = GetOpenDocumentIds();
            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            int modelType = swModel.GetType();

            if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(swDraw, out reference) && reference.Model != null &&
                    reference.Configuration != null)
                {
                    swModel = reference.Model;
                    swConf = reference.Configuration;
                    modelType = swModel.GetType();
                    _swApp.ActivateDoc(swModel.GetTitle());
                }
                else
                {
                    System.Windows.Forms.MessageBox.Show("No reference model found in the drawing.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }
            }

            if (swConf == null)
            {
                System.Windows.Forms.MessageBox.Show("No active configuration.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
            }

            ModelDoc2 rootModel = swModel;
            string rootTitle = swModel.GetTitle();

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
                    string zipFolderName = Path.GetFileName(exportTag);
                    string zipRoot = Path.Combine(
                        Path.GetDirectoryName(exportTag) ?? pubFolder,
                        zipFolderName + "_zip");
                    string innerFolder = Path.Combine(zipRoot, zipFolderName);
                    string bomInZip = Path.Combine(innerFolder, Path.GetFileName(bomFile));
                    string flatInZip = Path.Combine(innerFolder, Path.GetFileName(flatFile));

                    TryDeleteDirectory(zipRoot);
                    Directory.CreateDirectory(innerFolder);
                    MoveFileIfExists(bomFile, bomInZip);
                    MoveFileIfExists(flatFile, flatInZip);

                    if (File.Exists(zipPath))
                    {
                        File.Delete(zipPath);
                    }

                    CreateZipWithFolder(zipPath, zipFolderName, bomInZip, flatInZip);
                    TryDeleteDirectory(zipRoot);
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
            finally
            {
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
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
            string startTitle = string.Empty;

            try
            {
                ResetCancel();
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs, out startTitle);
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
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
            }
        }

        public void HideFeatures(HideFeaturesOptions options, Action<string> log, Action<int, int> progress)
        {
            if (options == null || options.FeatureMask == HideFeatureTypeFlags.None)
            {
                System.Windows.Forms.MessageBox.Show("No feature types selected.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            ModelDoc2 rootModel = null;
            string rootTitle = string.Empty;
            string startTitle = string.Empty;
            HashSet<string> initialDocs = null;
            string rootConfigName = string.Empty;
            string debugLogPath = EnableHideDebugLog
                ? Path.Combine(Path.GetTempPath(), "TinyMRP_hide_features.log")
                : string.Empty;

            try
            {
                ResetCancel();
                LogHideDebug(debugLogPath, "Start hide features.");
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs, out startTitle);
                if (entries.Count == 0)
                {
                    System.Windows.Forms.MessageBox.Show("No model entries to process.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }

                Configuration rootConfig = rootModel.GetActiveConfiguration() as Configuration;
                if (rootConfig != null)
                {
                    rootConfigName = rootConfig.Name;
                }

                int total = CalculateHideTotal(entries, options.AllConfigurations);
                UpdateProgress(progress, 0, total);

                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();

                    if (entry == null || entry.Model == null)
                    {
                        continue;
                    }

                    int docType = entry.Model.GetType();
                    if (docType != (int)swDocumentTypes_e.swDocPART &&
                        docType != (int)swDocumentTypes_e.swDocASSEMBLY)
                    {
                        continue;
                    }

                    string modelLabel = OnlyFile(entry.Model.GetPathName());
                    if (string.IsNullOrWhiteSpace(modelLabel))
                    {
                        modelLabel = entry.Model.GetTitle();
                    }

                    string[] configs = BuildConfigList(entry.Model, options.AllConfigurations, entry.ConfigurationName);
                    foreach (string configName in configs)
                    {
                        ThrowIfCancelled();
                        System.Windows.Forms.Application.DoEvents();

                        _swApp.ActivateDoc(entry.Model.GetTitle());
                        if (!string.IsNullOrWhiteSpace(configName))
                        {
                            entry.Model.ShowConfiguration2(configName);
                        }

                        LogHideDebug(debugLogPath, "Processing " + modelLabel + " [" + configName + "]");
                        if (EnableHideStatusLog)
                        {
                            Log(log, "Hide features: " + modelLabel + " [" + configName + "]");
                        }
                        try
                        {
                            HideFeaturesInModel(entry.Model, options.FeatureMask, debugLogPath);
                            if (options.HideEnvelopes && docType == (int)swDocumentTypes_e.swDocASSEMBLY)
                            {
                                HideEnvelopeComponents(entry.Model, debugLogPath);
                            }
                        }
                        catch (Exception ex)
                        {
                            LogHideDebug(debugLogPath, "Failed " + modelLabel + ": " + ex.Message);
                            if (EnableHideStatusLog)
                            {
                                Log(log, "Hide features failed: " + modelLabel + " (" + ex.Message + ")");
                            }
                        }

                        processed++;
                        UpdateProgress(progress, processed, total);
                    }

                    CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                }

                if (!string.IsNullOrWhiteSpace(rootConfigName))
                {
                    rootModel.ShowConfiguration2(rootConfigName);
                }

                LogHideDebug(debugLogPath, "Hide features finished.");
                System.Windows.Forms.MessageBox.Show("Hide features finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                LogHideDebug(debugLogPath, "Hide features cancelled.");
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                LogHideDebug(debugLogPath, "Hide features error: " + ex.Message);
                System.Windows.Forms.MessageBox.Show("Hide features failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
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
            string startTitle = string.Empty;

            try
            {
                ResetCancel();
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs, out startTitle);
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
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
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

        private bool TryGetActiveModel(out ModelDoc2 model, out Configuration config, out string startTitle)
        {
            model = _swApp.ActiveDoc as ModelDoc2;
            config = null;
            startTitle = string.Empty;
            if (model == null)
            {
                return false;
            }

            startTitle = model.GetTitle();
            config = model.GetActiveConfiguration() as Configuration;

            if (model.GetType() == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc draw = model as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(draw, out reference) && reference.Model != null)
                {
                    model = reference.Model;
                    config = reference.Configuration;
                    _swApp.ActivateDoc(model.GetTitle());
                }
            }

            return config != null;
        }

        private string[] BuildConfigList(ModelDoc2 model, bool allConfigs, string fallback)
        {
            if (model == null)
            {
                return new[] { fallback ?? string.Empty };
            }

            if (allConfigs)
            {
                string[] configs = ToStringArray(model.GetConfigurationNames());
                if (configs != null && configs.Length > 0)
                {
                    return configs;
                }
            }

            if (!string.IsNullOrWhiteSpace(fallback))
            {
                return new[] { fallback };
            }

            Configuration activeConfig = model.GetActiveConfiguration() as Configuration;
            if (activeConfig != null && !string.IsNullOrWhiteSpace(activeConfig.Name))
            {
                return new[] { activeConfig.Name };
            }

            return new[] { string.Empty };
        }

        private int CalculateHideTotal(List<ModelEntry> entries, bool allConfigs)
        {
            if (entries == null || entries.Count == 0)
            {
                return 1;
            }

            int total = 0;
            foreach (ModelEntry entry in entries)
            {
                if (entry == null || entry.Model == null)
                {
                    continue;
                }

                int docType = entry.Model.GetType();
                if (docType != (int)swDocumentTypes_e.swDocPART &&
                    docType != (int)swDocumentTypes_e.swDocASSEMBLY)
                {
                    continue;
                }

                string[] configs = BuildConfigList(entry.Model, allConfigs, entry.ConfigurationName);
                total += configs.Length > 0 ? configs.Length : 1;
            }

            return total > 0 ? total : 1;
        }

        private void HideFeaturesInModel(ModelDoc2 model, HideFeatureTypeFlags mask, string debugPath)
        {
            if (model == null)
            {
                return;
            }

            LogHideDebug(debugPath, "Collect features in " + model.GetTitle());

            ModelView view = model.ActiveView as ModelView;
            bool prevGraphics = view != null && view.EnableGraphicsUpdate;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = false;
            }

            var features = new List<Feature>();
            Feature first = model.FirstFeature() as Feature;
            CollectFeatures(first, mask, features, debugPath);
            LogHideDebug(debugPath, "Collected " + features.Count + " features in " + model.GetTitle());
            BlankFeatures(model, features, debugPath);

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = true;
            }

            if (view != null)
            {
                view.EnableGraphicsUpdate = prevGraphics;
            }

            if (!string.IsNullOrWhiteSpace(model.GetPathName()))
            {
                model.Save2(true);
            }
        }

        private void HideEnvelopeComponents(ModelDoc2 model, string debugPath)
        {
            if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                return;
            }

            Configuration conf = model.GetActiveConfiguration() as Configuration;
            Component2 root = conf != null ? conf.GetRootComponent() as Component2 : null;
            if (root == null)
            {
                return;
            }

            HideEnvelopeComponentsRecursive(root, debugPath);
        }

        private void HideEnvelopeComponentsRecursive(Component2 parent, string debugPath)
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
                if (child == null || child.IsSuppressed())
                {
                    continue;
                }

                bool isEnvelope = IsEnvelopeComponent(child);
                if (isEnvelope)
                {
                    bool hidden = TryHideComponent(child);
                    LogHideDebug(debugPath, "Hide envelope " + child.Name2 + " -> " + hidden);
                }

                HideEnvelopeComponentsRecursive(child, debugPath);
            }
        }

        private bool IsEnvelopeComponent(Component2 comp)
        {
            if (comp == null)
            {
                return false;
            }

            object target = comp;
            Type type = target.GetType();

            object result = TryInvokeMember(type, target, "IsEnvelope", BindingFlags.GetProperty | BindingFlags.InvokeMethod);
            if (result is bool)
            {
                return (bool)result;
            }

            if (result is int)
            {
                return (int)result != 0;
            }

            return false;
        }

        private bool TryHideComponent(Component2 comp)
        {
            if (comp == null)
            {
                return false;
            }

            object target = comp;
            Type type = target.GetType();

            if (TrySetMember(type, target, "Visible", false) ||
                TrySetMember(type, target, "Visible", 0))
            {
                return true;
            }

            if (TryInvokeVoidMember(type, target, "SetVisible", false) ||
                TryInvokeVoidMember(type, target, "SetVisible", 0))
            {
                return true;
            }

            if (TryInvokeVoidMember(type, target, "SetVisibility", 0))
            {
                return true;
            }

            return false;
        }

        private object TryInvokeMember(Type type, object target, string name, BindingFlags flags, params object[] args)
        {
            try
            {
                return type.InvokeMember(name, flags | BindingFlags.Instance | BindingFlags.Public, null, target, args);
            }
            catch
            {
                return null;
            }
        }

        private bool TryInvokeVoidMember(Type type, object target, string name, params object[] args)
        {
            try
            {
                type.InvokeMember(name, BindingFlags.InvokeMethod | BindingFlags.Instance | BindingFlags.Public,
                    null, target, args);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private bool TrySetMember(Type type, object target, string name, object value)
        {
            try
            {
                type.InvokeMember(name, BindingFlags.SetProperty | BindingFlags.Instance | BindingFlags.Public,
                    null, target, new[] { value });
                return true;
            }
            catch
            {
                return false;
            }
        }

        private void CollectFeatures(Feature feature, HideFeatureTypeFlags mask, List<Feature> result, string debugPath)
        {
            Feature current = feature;
            while (current != null)
            {
                try
                {
                    if (ShouldHideFeature(current, mask))
                    {
                        LogHideDebug(debugPath, "Queue feature " + SafeFeatureLabel(current));
                        result.Add(current);
                    }
                }
                catch (Exception ex)
                {
                    LogHideDebug(debugPath, "Feature check failed: " + ex.Message);
                }

                Feature next = null;
                try
                {
                    next = current.GetNextFeature() as Feature;
                }
                catch (Exception ex)
                {
                    LogHideDebug(debugPath, "GetNextFeature failed: " + ex.Message);
                    next = null;
                }

                current = next;
            }
        }

        private bool ShouldHideFeature(Feature feature, HideFeatureTypeFlags mask)
        {
            if (feature == null)
            {
                return false;
            }

            int visible = feature.Visible;
            if (visible != (int)swVisibilityState_e.swVisibilityStateShown &&
                visible != (int)swVisibilityState_e.swVisibilityStateUnknown)
            {
                return false;
            }

            string typeName = feature.GetTypeName();
            HideFeatureTypeFlags typeFlag = MapFeatureType(typeName);
            return typeFlag != HideFeatureTypeFlags.None && (mask & typeFlag) == typeFlag;
        }

        private HideFeatureTypeFlags MapFeatureType(string typeName)
        {
            switch (typeName)
            {
                case "OriginProfileFeature":
                    return HideFeatureTypeFlags.Origin;
                case "RefPlane":
                    return HideFeatureTypeFlags.RefPlane;
                case "RefAxis":
                    return HideFeatureTypeFlags.RefAxis;
                case "RefPoint":
                    return HideFeatureTypeFlags.RefPoint;
                case "CoordSys":
                    return HideFeatureTypeFlags.CoordSys;
                case "ProfileFeature":
                    return HideFeatureTypeFlags.Sketch2D;
                case "3DProfileFeature":
                    return HideFeatureTypeFlags.Sketch3D;
                case "3DSplineCurve":
                    return HideFeatureTypeFlags.Spline3D;
                case "CompositeCurve":
                    return HideFeatureTypeFlags.CompositeCurve;
                case "Helix":
                    return HideFeatureTypeFlags.Helix;
                default:
                    return HideFeatureTypeFlags.None;
            }
        }

        private void BlankFeatures(ModelDoc2 model, List<Feature> features, string debugPath)
        {
            if (model == null || features == null || features.Count == 0)
            {
                return;
            }

            int count = 0;
            bool append = false;

            foreach (Feature feat in features)
            {
                if (feat == null)
                {
                    continue;
                }

                LogHideDebug(debugPath, "Select feature " + SafeFeatureLabel(feat));
                bool selected = false;
                try
                {
                    selected = feat.Select2(append, 0);
                }
                catch
                {
                    selected = false;
                }

                if (!selected)
                {
                    append = false;
                    continue;
                }

                count++;
                append = true;

                if (count % 25 == 0)
                {
                    LogHideDebug(debugPath, "Blank batch at " + count);
                    try
                    {
                        model.BlankRefGeom();
                        model.BlankSketch();
                    }
                    catch (Exception ex)
                    {
                        LogHideDebug(debugPath, "Blank batch failed: " + ex.Message);
                    }
                    append = false;
                }
            }

            LogHideDebug(debugPath, "Blank final at " + count);
            try
            {
                model.BlankRefGeom();
                model.BlankSketch();
            }
            catch (Exception ex)
            {
                LogHideDebug(debugPath, "Blank final failed: " + ex.Message);
            }

            if (features.Count > 0)
            {
                Feature first = features[0];
                try
                {
                    first.Select2(false, 0);
                    first.DeSelect();
                }
                catch (Exception ex)
                {
                    LogHideDebug(debugPath, "Deselect failed: " + ex.Message);
                }
            }
        }

        private string SafeFeatureLabel(Feature feature)
        {
            if (feature == null)
            {
                return "<null>";
            }

            string name = string.Empty;
            try
            {
                name = feature.Name;
            }
            catch
            {
                name = string.Empty;
            }

            string type = string.Empty;
            try
            {
                type = feature.GetTypeName();
            }
            catch
            {
                type = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(name))
            {
                name = "<unnamed>";
            }

            if (string.IsNullOrWhiteSpace(type))
            {
                type = "<unknown>";
            }

            return name + " [" + type + "]";
        }

        private string TraverseModel(bool createFiles, string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress, Action<int, int> deliverablesProgress)
        {
            HashSet<string> ignored;
            return TraverseModel(createFiles, exportTag, options, log, flatBomProgress, deliverablesProgress, out ignored);
        }

        private string TraverseModel(bool createFiles, string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress, Action<int, int> deliverablesProgress, out HashSet<string> uploadPackBases)
        {
            uploadPackBases = null;
            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            string startTitle = swModel.GetTitle();
            HashSet<string> initialDocs = GetOpenDocumentIds();

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
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

            if (swConf == null)
            {
                throw new InvalidOperationException("No active configuration.");
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
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

                var entries = BuildBatchEntries(swModel, swConf, modelType, options.TopLevelOnly);

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

                uploadPackBases = createFiles
                    ? new HashSet<string>(StringComparer.OrdinalIgnoreCase)
                    : null;

                UpdateProgress(flatBomProgress, 0, entries.Count);
                WriteFlatBom(outputFile, entries, log, flatBomProgress, initialDocs, rootModel, rootTitle, uploadPackBases);
                ThrowIfCancelled();

                if (createFiles)
                {
                    UpdateProgress(deliverablesProgress, 0, entries.Count);
                    int processed = 0;
                    foreach (BatchEntry entry in entries)
                    {
                        ThrowIfCancelled();
                        bool openedHere;
                        ModelDoc2 model = ResolveBatchModel(entry, rootModel, out openedHere);
                        if (model != null)
                        {
                            ProcessDeliverables(model, entry.ConfigurationName, deliverablesFolder, options, log);
                            CloseBatchModel(model, entry, initialDocs, rootModel, rootTitle, openedHere);
                            CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                        }
                        processed++;
                        UpdateProgress(deliverablesProgress, processed, entries.Count);
                    }
                }

                return outputFile;
            }
            finally
            {
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
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
            }
        }

        private void CreateUploadPack(string flatBomPath, HashSet<string> uploadPackBases, PublishOptions options, Action<string> log)
        {
            if (string.IsNullOrWhiteSpace(flatBomPath))
            {
                Log(log, "Upload pack skipped: missing flat BOM path.");
                return;
            }

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                Log(log, "Upload pack skipped: no active model.");
                return;
            }

            Configuration config = swModel.GetActiveConfiguration() as Configuration;
            if (config == null)
            {
                Log(log, "Upload pack skipped: no active configuration.");
                return;
            }

            string treeBomPath = BuildTreeBomPath(flatBomPath);
            TryBuildTreeBom(swModel, treeBomPath, log);

            AssociatedFilesPayload payload = ReadAssociatedFiles(swModel, config.Name);
            string partProp = _config != null ? _config.PartNumberProperty : "PartNumber";
            string revProp = _config != null ? _config.RevisionProperty : "Revision";
            if (string.IsNullOrWhiteSpace(partProp))
            {
                partProp = "PartNumber";
            }
            if (string.IsNullOrWhiteSpace(revProp))
            {
                revProp = "Revision";
            }

            string pn = payload.PartNumber;
            if (string.IsNullOrWhiteSpace(pn))
            {
                pn = GetEvalProperty(swModel, config.Name, partProp);
                if (string.IsNullOrWhiteSpace(pn))
                {
                    pn = GetEvalProperty(swModel, string.Empty, partProp);
                }
            }

            string rev = payload.Revision;
            if (string.IsNullOrWhiteSpace(rev))
            {
                rev = GetEvalProperty(swModel, config.Name, revProp);
                if (string.IsNullOrWhiteSpace(rev))
                {
                    rev = GetEvalProperty(swModel, string.Empty, revProp);
                }
            }

            string deliverablesRoot = EnsureTrailingSlash(options.DeliverablesFolder);
            if (string.IsNullOrWhiteSpace(deliverablesRoot))
            {
                Log(log, "Upload pack skipped: deliverables folder missing.");
                return;
            }
            deliverablesRoot = deliverablesRoot.TrimEnd('\\', '/');

            string zipName = GetFileString(swModel, config.Name) + "_UPLOADPACK.zip";
            string zipPath = Path.Combine(deliverablesRoot, zipName);

            UploadPackBuilder.Build(
                zipPath,
                deliverablesRoot,
                flatBomPath,
                treeBomPath,
                pn,
                rev,
                payload.Files,
                log,
                uploadPackBases);

            Log(log, "Upload pack created: " + zipPath);
        }

        private AssociatedFilesPayload ReadAssociatedFiles(ModelDoc2 model, string configName)
        {
            if (model == null)
            {
                return new AssociatedFilesPayload();
            }

            string raw = GetEvalProperty(model, string.Empty, AssociatedFilesPayload.PropertyName);
            AssociatedFilesPayload payload = AssociatedFilesPayload.FromJson(raw);
            if (payload.Files == null)
            {
                payload.Files = new List<AssociatedFileEntry>();
            }
            return payload;
        }

        private string BuildTreeBomPath(string flatBomPath)
        {
            if (string.IsNullOrWhiteSpace(flatBomPath))
            {
                return string.Empty;
            }

            const string suffix = "_FLATBOM.txt";
            if (flatBomPath.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
            {
                return flatBomPath.Substring(0, flatBomPath.Length - suffix.Length) + "_TREEBOM.txt";
            }
            return flatBomPath + "_TREEBOM.txt";
        }

        private bool TryBuildTreeBom(ModelDoc2 rootModel, string treeBomPath, Action<string> log)
        {
            if (rootModel == null || string.IsNullOrWhiteSpace(treeBomPath))
            {
                return false;
            }

            string modelPath = rootModel.GetPathName();
            if (string.IsNullOrWhiteSpace(modelPath))
            {
                Log(log, "Upload pack: active document must be saved to build TREEBOM.");
                return false;
            }

            string template = _swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly);
            ModelDoc2 assyDoc = _swApp.NewDocument(template, 0, 0, 0) as ModelDoc2;
            AssemblyDoc swAssembly = assyDoc as AssemblyDoc;
            if (assyDoc == null || swAssembly == null)
            {
                Log(log, "Upload pack: failed to create temp assembly for TREEBOM.");
                return false;
            }

            try
            {
                _swApp.ActivateDoc(assyDoc.GetTitle());
                swAssembly.AddComponent5(modelPath, 0, string.Empty, false, string.Empty, 0, 0, 0);
                ModelDoc2 assyModel = _swApp.ActiveDoc as ModelDoc2;
                if (assyModel == null)
                {
                    Log(log, "Upload pack: failed to activate temp assembly.");
                    return false;
                }

                Configuration assyConfig = assyModel.GetActiveConfiguration() as Configuration;
                if (assyConfig == null)
                {
                    Log(log, "Upload pack: failed to read assembly configuration.");
                    return false;
                }

                SetUnitPreferences(rootModel);

                string treeDir = Path.GetDirectoryName(treeBomPath);
                if (!string.IsNullOrWhiteSpace(treeDir))
                {
                    Directory.CreateDirectory(treeDir);
                }
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
                    tableAnn.SaveAsText(treeBomPath, "\t");
                    return true;
                }

                Log(log, "Upload pack: failed to create BOM table.");
                return false;
            }
            finally
            {
                _swApp.CloseDoc(assyDoc.GetTitle());
            }
        }

        private List<ModelEntry> GetEntriesForActiveDoc(bool includeChildren, out ModelDoc2 rootModel,
            out string rootTitle, out HashSet<string> initialDocs, out string startTitle)
        {
            ThrowIfCancelled();

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            startTitle = swModel.GetTitle();
            initialDocs = GetOpenDocumentIds();

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
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

            if (swConf == null)
            {
                throw new InvalidOperationException("No active configuration.");
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
            }

            rootModel = swModel;
            rootTitle = swModel.GetTitle();

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

        private List<BatchEntry> BuildBatchEntries(ModelDoc2 rootModel, Configuration rootConfig, int modelType, bool topLevelOnly)
        {
            var entries = new List<BatchEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            string rootConfigName = rootConfig != null ? rootConfig.Name : string.Empty;
            AddBatchEntry(rootModel.GetPathName(), rootModel.GetTitle(), rootConfigName, true, entries, seen, false);

            if (modelType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                AssemblyDoc assy = rootModel as AssemblyDoc;
                if (assy != null)
                {
                    assy.ResolveAllLightWeightComponents(true);
                }
                if (!topLevelOnly && rootConfig != null)
                {
                    Component2 root = rootConfig.GetRootComponent() as Component2;
                    TraverseComponentRefs(root, entries, seen);
                }
            }

            return entries;
        }

        private void AddBatchEntry(string path, string title, string configName, bool isRoot,
            List<BatchEntry> entries, HashSet<string> seen, bool prepend)
        {
            ThrowIfCancelled();
            string keyPath = !string.IsNullOrWhiteSpace(path) ? path : (title ?? string.Empty);
            string key = keyPath + "|" + (configName ?? string.Empty);
            if (!seen.Add(key))
            {
                return;
            }

            var entry = new BatchEntry
            {
                ModelPath = path ?? string.Empty,
                ModelTitle = title ?? string.Empty,
                ConfigurationName = configName ?? string.Empty,
                IsRoot = isRoot
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

        private void TraverseComponentRefs(Component2 parent, List<BatchEntry> entries, HashSet<string> seen)
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

                string confName = child.ReferencedConfiguration;
                string path = string.Empty;
                string title = string.Empty;
                try
                {
                    path = child.GetPathName();
                }
                catch
                {
                    path = string.Empty;
                }

                if (string.IsNullOrWhiteSpace(path))
                {
                    ModelDoc2 childModel = child.GetModelDoc2() as ModelDoc2;
                    if (childModel != null)
                    {
                        try
                        {
                            path = childModel.GetPathName();
                            title = childModel.GetTitle();
                        }
                        catch
                        {
                            path = string.Empty;
                        }
                    }
                }

                AddBatchEntry(path, title, confName, false, entries, seen, true);
                TraverseComponentRefs(child, entries, seen);
            }
        }

        private ModelDoc2 ResolveBatchModel(BatchEntry entry, ModelDoc2 rootModel, out bool openedHere)
        {
            openedHere = false;
            if (entry == null)
            {
                return null;
            }
            if (entry.IsRoot && rootModel != null)
            {
                TryShowConfiguration(rootModel, entry.ConfigurationName);
                return rootModel;
            }

            ModelDoc2 openDoc = FindOpenDocument(entry.ModelPath, entry.ModelTitle);
            if (openDoc != null)
            {
                TryShowConfiguration(openDoc, entry.ConfigurationName);
                return openDoc;
            }

            if (!string.IsNullOrWhiteSpace(entry.ModelPath) && File.Exists(entry.ModelPath))
            {
                int errors = 0;
                int warnings = 0;
                int docType = DocumentTypeFromPath(entry.ModelPath);
                ModelDoc2 opened = _swApp.OpenDoc6(entry.ModelPath, docType,
                    (int)swOpenDocOptions_e.swOpenDocOptions_Silent, string.Empty, ref errors, ref warnings) as ModelDoc2;
                if (opened != null)
                {
                    openedHere = true;
                    TryShowConfiguration(opened, entry.ConfigurationName);
                }
                return opened;
            }

            return null;
        }

        private ModelDoc2 FindOpenDocument(string path, string title)
        {
            object docsObj = _swApp.GetDocuments();
            object[] docs = docsObj as object[];
            if (docs == null)
            {
                return null;
            }

            foreach (object obj in docs)
            {
                ModelDoc2 doc = obj as ModelDoc2;
                if (doc == null)
                {
                    continue;
                }

                try
                {
                    string docPath = doc.GetPathName();
                    if (!string.IsNullOrWhiteSpace(path) &&
                        !string.IsNullOrWhiteSpace(docPath) &&
                        string.Equals(docPath, path, StringComparison.OrdinalIgnoreCase))
                    {
                        return doc;
                    }

                    if (string.IsNullOrWhiteSpace(path) && !string.IsNullOrWhiteSpace(title))
                    {
                        string docTitle = doc.GetTitle();
                        if (!string.IsNullOrWhiteSpace(docTitle) &&
                            string.Equals(docTitle, title, StringComparison.OrdinalIgnoreCase))
                        {
                            return doc;
                        }
                    }
                }
                catch
                {
                    // ignore lookup errors
                }
            }

            return null;
        }

        private void CloseBatchModel(ModelDoc2 model, BatchEntry entry, HashSet<string> initialDocs,
            ModelDoc2 rootModel, string rootTitle, bool openedHere)
        {
            if (model == null || entry == null)
            {
                return;
            }

            if (entry.IsRoot || ReferenceEquals(model, rootModel))
            {
                return;
            }

            string id = GetDocumentId(model);
            if (!string.IsNullOrWhiteSpace(id) && initialDocs != null && initialDocs.Contains(id))
            {
                return;
            }

            string title = string.Empty;
            try
            {
                title = model.GetTitle();
            }
            catch
            {
                title = string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(rootTitle) &&
                string.Equals(title, rootTitle, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            if (!openedHere && !string.IsNullOrWhiteSpace(id) && initialDocs != null && initialDocs.Contains(id))
            {
                return;
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

        private int DocumentTypeFromPath(string path)
        {
            string ext = Path.GetExtension(path ?? string.Empty).ToLowerInvariant();
            if (ext == ".sldasm")
            {
                return (int)swDocumentTypes_e.swDocASSEMBLY;
            }
            if (ext == ".slddrw")
            {
                return (int)swDocumentTypes_e.swDocDRAWING;
            }
            return (int)swDocumentTypes_e.swDocPART;
        }

        private void TryShowConfiguration(ModelDoc2 model, string configName)
        {
            if (model == null || string.IsNullOrWhiteSpace(configName))
            {
                return;
            }

            try
            {
                model.ShowConfiguration2(configName);
            }
            catch
            {
                // ignore config switch errors
            }
        }

        private void WriteFlatBom(string outputFile, List<BatchEntry> entries, Action<string> log,
            Action<int, int> progress, HashSet<string> initialDocs, ModelDoc2 rootModel, string rootTitle,
            HashSet<string> uploadPackBases)
        {
            using (var writer = new StreamWriter(outputFile, false, Encoding.UTF8))
            {
                int processed = 0;
                foreach (BatchEntry entry in entries)
                {
                    ThrowIfCancelled();
                    bool openedHere;
                    ModelDoc2 model = ResolveBatchModel(entry, rootModel, out openedHere);
                    if (model == null)
                    {
                        processed++;
                        UpdateProgress(progress, processed, entries.Count);
                        continue;
                    }
                    try
                    {
                        writer.WriteLine(GetDocDict(model, entry.ConfigurationName));
                        if (uploadPackBases != null)
                        {
                            string fileKey = GetFileString(model, entry.ConfigurationName);
                            if (!string.IsNullOrWhiteSpace(fileKey))
                            {
                                uploadPackBases.Add(fileKey);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Log(log, "Error building properties for model: " + ex.Message);
                        try
                        {
                            Configuration entryConf = model.GetConfigurationByName(entry.ConfigurationName) as Configuration;
                            string fallback = "{'partnumber':'" +
                                              SanitizeString(BomPartNumber(entryConf, model)) + "'}";
                            writer.WriteLine(fallback);
                        }
                        catch
                        {
                            writer.WriteLine("{'partnumber':''}");
                        }
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                    CloseBatchModel(model, entry, initialDocs, rootModel, rootTitle, openedHere);
                }
            }
        }

        private void ProcessDeliverables(ModelDoc2 model, string confName, string deliverablesFolder, PublishOptions options, Action<string> log)
        {
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

                bool createPly = options.ExportPly &&
                                 ShouldExport(Path.Combine(deliverablesFolder, "ply", fileString + ".ply"),
                                     options.OverwriteFiles);

                bool createStl = options.ExportStl &&
                                 ShouldExport(Path.Combine(deliverablesFolder, "stl", fileString + ".stl"),
                                     options.OverwriteFiles);

                bool createEdr = options.ExportEdrawing &&
                                 ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString +
                                     (model.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt")),
                                     options.OverwriteFiles);

                if (createPng || createStep || createEdr || create3mf || createPly || createStl)
                {
                    ModelPublish(model, confName, fileString, deliverablesFolder, createPng, createStep, createEdr,
                        create3mf, createPly, createStl, log);
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
                "ply",
                "stl",
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
            bool png, bool step, bool edr, bool threeMf, bool ply, bool stl, Action<string> log)
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

            bool stlExported = false;
            string stlPath = Path.Combine(deliverablesFolder, "stl", fileString + ".stl");
            if (stl)
            {
                stlExported = model.Extension.SaveAs(stlPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                stlExported = stlExported && File.Exists(stlPath);
            }

            if (ply)
            {
                string plyPath = Path.Combine(deliverablesFolder, "ply", fileString + ".ply");
                bool plyExported = model.Extension.SaveAs(plyPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                plyExported = plyExported && File.Exists(plyPath);

                if (!plyExported)
                {
                    string sourceStl = stlExported ? stlPath : string.Empty;
                    string tempStl = string.Empty;

                    if (string.IsNullOrWhiteSpace(sourceStl))
                    {
                        tempStl = Path.Combine(Path.GetTempPath(),
                            fileString + "_" + Guid.NewGuid().ToString("N") + ".stl");
                        bool tempOk = model.Extension.SaveAs(tempStl, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (tempOk && File.Exists(tempStl))
                        {
                            sourceStl = tempStl;
                        }
                    }

                    if (!string.IsNullOrWhiteSpace(sourceStl) && File.Exists(sourceStl))
                    {
                        if (!TryConvertStlToPly(sourceStl, plyPath))
                        {
                            Log(log, "PLY export failed: STL conversion failed.");
                        }
                    }
                    else
                    {
                        Log(log, "PLY export failed: STL source unavailable.");
                    }

                    if (!string.IsNullOrWhiteSpace(tempStl))
                    {
                        try
                        {
                            File.Delete(tempStl);
                        }
                        catch
                        {
                            // ignore cleanup errors
                        }
                    }
                }
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

        private bool TryConvertStlToPly(string stlPath, string plyPath)
        {
            try
            {
                List<float> vertices;
                if (!TryReadBinaryStlVertices(stlPath, out vertices) &&
                    !TryReadAsciiStlVertices(stlPath, out vertices))
                {
                    return false;
                }

                int vertexCount = vertices.Count / 3;
                int faceCount = vertexCount / 3;
                if (faceCount <= 0)
                {
                    return false;
                }

                vertexCount = faceCount * 3;
                int floatCount = vertexCount * 3;

                using (var stream = new FileStream(plyPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var writer = new BinaryWriter(stream))
                {
                    string header = BuildPlyHeader(vertexCount, faceCount);
                    writer.Write(Encoding.ASCII.GetBytes(header));

                    for (int i = 0; i < floatCount; i++)
                    {
                        writer.Write(vertices[i]);
                    }

                    for (int i = 0; i < faceCount; i++)
                    {
                        writer.Write((byte)3);
                        writer.Write(i * 3);
                        writer.Write(i * 3 + 1);
                        writer.Write(i * 3 + 2);
                    }
                }

                return File.Exists(plyPath);
            }
            catch
            {
                return false;
            }
        }

        private bool TryReadBinaryStlVertices(string path, out List<float> vertices)
        {
            vertices = null;
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var reader = new BinaryReader(stream))
            {
                if (stream.Length < 84)
                {
                    return false;
                }

                reader.ReadBytes(80);
                uint triCount = reader.ReadUInt32();
                long expectedSize = 84L + (50L * triCount);
                if (expectedSize != stream.Length)
                {
                    return false;
                }

                vertices = new List<float>(checked((int)triCount * 9));
                for (uint i = 0; i < triCount; i++)
                {
                    reader.ReadSingle();
                    reader.ReadSingle();
                    reader.ReadSingle();

                    for (int v = 0; v < 3; v++)
                    {
                        vertices.Add(reader.ReadSingle());
                        vertices.Add(reader.ReadSingle());
                        vertices.Add(reader.ReadSingle());
                    }

                    reader.ReadUInt16();
                }
            }

            return vertices.Count >= 9;
        }

        private bool TryReadAsciiStlVertices(string path, out List<float> vertices)
        {
            vertices = new List<float>();
            foreach (string raw in File.ReadLines(path))
            {
                string line = raw.Trim();
                if (!line.StartsWith("vertex", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 4)
                {
                    continue;
                }

                float x;
                float y;
                float z;
                if (float.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out x) &&
                    float.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out y) &&
                    float.TryParse(parts[3], NumberStyles.Float, CultureInfo.InvariantCulture, out z))
                {
                    vertices.Add(x);
                    vertices.Add(y);
                    vertices.Add(z);
                }
            }

            return vertices.Count >= 9;
        }

        private string BuildPlyHeader(int vertexCount, int faceCount)
        {
            var sb = new StringBuilder();
            sb.Append("ply\n");
            sb.Append("format binary_little_endian 1.0\n");
            sb.Append("element vertex ").Append(vertexCount).Append("\n");
            sb.Append("property float x\n");
            sb.Append("property float y\n");
            sb.Append("property float z\n");
            sb.Append("element face ").Append(faceCount).Append("\n");
            sb.Append("property list uchar int vertex_indices\n");
            sb.Append("end_header\n");
            return sb.ToString();
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
            string tempRev = (GetEvalProperty(model, configName, "revision") ?? string.Empty).Trim();
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

        private bool HasCustomProperty(ModelDoc2 model, string confName, string property)
        {
            if (model == null || string.IsNullOrWhiteSpace(property))
            {
                return false;
            }

            string[] names = GetCustomPropertyNames(model, confName);
            if (names == null || names.Length == 0)
            {
                return false;
            }

            foreach (string name in names)
            {
                if (string.Equals(name, property, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
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

            bool hasConfigProperty = !string.IsNullOrEmpty(confName) &&
                HasCustomProperty(model, confName, property);

            if (string.Equals(property, "revision", StringComparison.OrdinalIgnoreCase) &&
                string.IsNullOrEmpty(resolved) &&
                !string.IsNullOrEmpty(confName) &&
                !hasConfigProperty)
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

        private void LogHideDebug(string path, string message)
        {
            if (!EnableHideDebugLog || string.IsNullOrWhiteSpace(path))
            {
                return;
            }

            try
            {
                File.AppendAllText(path, DateTime.Now.ToString("s") + " " + message + System.Environment.NewLine);
            }
            catch
            {
                // ignore logging errors
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

        private void CreateZipWithFolder(string zipPath, string folderName, params string[] filePaths)
        {
            string normalizedFolder = (folderName ?? string.Empty).Trim();
            normalizedFolder = normalizedFolder.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            using (var stream = new FileStream(zipPath, FileMode.Create, FileAccess.Write, FileShare.None))
            using (var archive = new ZipArchive(stream, ZipArchiveMode.Create, false, Encoding.UTF8))
            {
                if (!string.IsNullOrWhiteSpace(normalizedFolder))
                {
                    archive.CreateEntry(normalizedFolder + "/");
                }

                foreach (string filePath in filePaths)
                {
                    if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
                    {
                        continue;
                    }

                    string entryName = string.IsNullOrWhiteSpace(normalizedFolder)
                        ? Path.GetFileName(filePath)
                        : normalizedFolder + "/" + Path.GetFileName(filePath);

                    archive.CreateEntryFromFile(filePath, entryName, CompressionLevel.Optimal);
                }
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

        private void RestoreStartDocument(string startTitle)
        {
            if (!string.IsNullOrWhiteSpace(startTitle))
            {
                _swApp.ActivateDoc(startTitle);
            }
        }

        private void CloseModelIfNotInitiallyOpen(HashSet<string> initialDocs, ModelDoc2 model, string startTitle)
        {
            if (model == null || initialDocs == null)
            {
                return;
            }

            string id = GetDocumentId(model);
            if (!string.IsNullOrWhiteSpace(id) && initialDocs.Contains(id))
            {
                return;
            }

            string title = model.GetTitle();
            if (string.IsNullOrWhiteSpace(title))
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(startTitle) &&
                string.Equals(title, startTitle, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            try
            {
                _swApp.CloseDoc(title);
            }
            catch
            {
                // ignore close errors
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
