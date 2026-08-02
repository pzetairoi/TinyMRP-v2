using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class PublisherTests
    {
        [TestMethod]
        public void EnsureMediaFolders_CreatesPlyAndStl()
        {
            var config = new TinyMrpConfig();
            var publisher = new TinyMrpPublisher(null, config);
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_test_" + Guid.NewGuid().ToString("N"));

            try
            {
                Directory.CreateDirectory(root);
                InvokePrivate(publisher, "EnsureMediaFolders", root);

                Assert.IsTrue(Directory.Exists(Path.Combine(root, "ply")));
                Assert.IsTrue(Directory.Exists(Path.Combine(root, "stl")));
            }
            finally
            {
                if (Directory.Exists(root))
                {
                    Directory.Delete(root, true);
                }
            }
        }

        [TestMethod]
        public void TryConvertStlToPly_WritesBinaryPlyHeader()
        {
            var config = new TinyMrpConfig();
            var publisher = new TinyMrpPublisher(null, config);
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_test_" + Guid.NewGuid().ToString("N"));
            string stlPath = Path.Combine(root, "triangle.stl");
            string plyPath = Path.Combine(root, "triangle.ply");

            try
            {
                Directory.CreateDirectory(root);
                File.WriteAllText(stlPath, BuildAsciiStl(), Encoding.ASCII);

                bool converted = (bool)InvokePrivate(publisher, "TryConvertStlToPly", stlPath, plyPath);
                Assert.IsTrue(converted);

                var headerLines = new List<string>();
                using (var stream = new FileStream(plyPath, FileMode.Open, FileAccess.Read, FileShare.Read))
                using (var reader = new StreamReader(stream, Encoding.ASCII, false, 1024, true))
                {
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        headerLines.Add(line);
                        if (string.Equals(line, "end_header", StringComparison.Ordinal))
                        {
                            break;
                        }
                    }
                }

                string header = string.Join("\n", headerLines);
                Assert.IsTrue(header.Contains("element vertex 3"));
                Assert.IsTrue(header.Contains("element face 1"));
            }
            finally
            {
                if (Directory.Exists(root))
                {
                    Directory.Delete(root, true);
                }
            }
        }

        [TestMethod]
        public void IsValidPlyFile_ValidAsciiWithVertices_ReturnsTrue()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string plyPath = Path.Combine(root, "valid_ascii.ply");

            try
            {
                File.WriteAllText(plyPath, BuildValidAsciiPly(), Encoding.ASCII);

                string reason;
                bool valid = InvokePrivateWithOutString(publisher, "IsValidPlyFile", plyPath, out reason);

                Assert.IsTrue(valid);
                Assert.AreEqual(string.Empty, reason);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void IsValidPlyFile_HeaderOnly_ReturnsFalse()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string plyPath = Path.Combine(root, "header_only.ply");

            try
            {
                File.WriteAllText(plyPath, BuildHeaderOnlyPly(3), Encoding.ASCII);

                string reason;
                bool valid = InvokePrivateWithOutString(publisher, "IsValidPlyFile", plyPath, out reason);

                Assert.IsFalse(valid);
                Assert.AreEqual("header-only file", reason);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void IsValidPlyFile_ZeroVertices_ReturnsFalse()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string plyPath = Path.Combine(root, "zero_vertices.ply");

            try
            {
                File.WriteAllText(plyPath, BuildHeaderOnlyPly(0), Encoding.ASCII);

                string reason;
                bool valid = InvokePrivateWithOutString(publisher, "IsValidPlyFile", plyPath, out reason);

                Assert.IsFalse(valid);
                Assert.AreEqual("header has zero vertices", reason);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void IsValidPlyFile_MissingEndHeader_ReturnsFalse()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string plyPath = Path.Combine(root, "missing_end_header.ply");

            try
            {
                File.WriteAllText(
                    plyPath,
                    "ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\n0 0 0\n1 0 0\n0 1 0\n",
                    Encoding.ASCII);

                string reason;
                bool valid = InvokePrivateWithOutString(publisher, "IsValidPlyFile", plyPath, out reason);

                Assert.IsFalse(valid);
                Assert.AreEqual("missing end_header", reason);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void IsValidPlyFile_NonPly_ReturnsFalse()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string plyPath = Path.Combine(root, "not_ply.ply");

            try
            {
                File.WriteAllText(plyPath, "notply\nend_header\nbody\n", Encoding.ASCII);

                string reason;
                bool valid = InvokePrivateWithOutString(publisher, "IsValidPlyFile", plyPath, out reason);

                Assert.IsFalse(valid);
                Assert.AreEqual("first line does not start with ply", reason);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void ValidateExportedOutput_UsesPlyValidationAndGenericThresholds()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string validPlyPath = Path.Combine(root, "valid.ply");
            string tinyStlPath = Path.Combine(root, "tiny.stl");
            string validStlPath = Path.Combine(root, "valid.stl");

            try
            {
                File.WriteAllText(validPlyPath, BuildValidAsciiPly(), Encoding.ASCII);
                File.WriteAllText(tinyStlPath, "solid x\nendsolid x\n", Encoding.ASCII);
                File.WriteAllText(validStlPath, BuildAsciiStl() + new string(' ', 256), Encoding.ASCII);

                string reason;
                bool validPly = InvokePrivateValidateExportedOutput(publisher, "ply", validPlyPath, out reason);
                Assert.IsTrue(validPly);
                Assert.AreEqual(string.Empty, reason);

                bool tinyStlValid = InvokePrivateValidateExportedOutput(publisher, "stl", tinyStlPath, out reason);
                Assert.IsFalse(tinyStlValid);
                Assert.AreEqual("file too small", reason);

                bool validStl = InvokePrivateValidateExportedOutput(publisher, "stl", validStlPath, out reason);
                Assert.IsTrue(validStl);
                Assert.AreEqual(string.Empty, reason);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void TryPrepareExportOutput_ValidExistingFileAndNoOverwrite_SkipsExport()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            object summary = Activator.CreateInstance(GetNestedType("ExportSummary"));
            SetPrivateField(publisher, "_currentExportSummary", summary);
            string root = CreateTempRoot();
            string finalPath = Path.Combine(root, "valid.stl");
            var messages = new List<string>();

            try
            {
                File.WriteAllText(finalPath, BuildAsciiStl() + new string(' ', 256), Encoding.ASCII);

                object[] args = { "stl", finalPath, false, new Action<string>(messages.Add), null, false, null, null };
                bool ok = (bool)InvokePrivate(publisher, "TryPrepareExportOutput", args);

                Assert.IsTrue(ok);
                Assert.AreEqual(true, args[5]);
                Assert.AreEqual("existing valid output", args[6]);
                Assert.AreEqual(string.Empty, args[4] as string ?? string.Empty);
                Assert.AreEqual(string.Empty, args[7] as string ?? string.Empty);
                object existingPaths = GetField(summary, "ExistingOutputPaths");
                Assert.AreEqual(1, existingPaths.GetType().GetProperty("Count").GetValue(existingPaths));
                Assert.AreEqual(0, InvokePrivate(publisher, "GetDeliverableFailureFormatCount", summary));
                Assert.IsTrue(messages.Exists(message => message.Contains("skipped (already exists)")));

                messages.Clear();
                InvokePrivate(publisher, "WriteDeliverablesFailureSummary", new Action<string>(messages.Add), summary);
                Assert.AreEqual("===== ACTUAL FAILED EXPORTS =====", messages[0]);
                Assert.AreEqual("None.", messages[1]);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void TryPrepareExportOutput_InvalidExistingFile_IsQuarantinedAndExportPrepared()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string finalPath = Path.Combine(root, "invalid.stl");

            try
            {
                File.WriteAllText(finalPath, "solid x\nendsolid x\n", Encoding.ASCII);

                object[] args = { "stl", finalPath, false, null, null, false, null, null };
                bool ok = (bool)InvokePrivate(publisher, "TryPrepareExportOutput", args);

                Assert.IsTrue(ok);
                Assert.AreEqual(false, args[5]);
                Assert.AreEqual("file too small", args[6]);
                Assert.IsFalse(string.IsNullOrWhiteSpace(args[4] as string));
                Assert.AreEqual(finalPath + ".bad", args[7]);
                Assert.IsFalse(File.Exists(finalPath));
                Assert.IsTrue(File.Exists(finalPath + ".bad"));
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void TryFinalizeExportedTempFile_InvalidTemp_DoesNotReplaceValidFinal()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string finalPath = Path.Combine(root, "final.stl");
            string tempPath = Path.Combine(root, "temp.stl");

            try
            {
                string validContents = BuildAsciiStl() + new string(' ', 256);
                File.WriteAllText(finalPath, validContents, Encoding.ASCII);
                File.WriteAllText(tempPath, "solid x\nendsolid x\n", Encoding.ASCII);

                object result = InvokePrivate(publisher, "TryFinalizeExportedTempFile", "stl", tempPath, finalPath, null);

                Assert.AreEqual(false, GetField(result, "Success"));
                Assert.AreEqual("file too small", GetField(result, "Reason"));
                Assert.AreEqual(validContents, File.ReadAllText(finalPath, Encoding.ASCII));
                Assert.IsFalse(File.Exists(tempPath));
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void ValidateRequestedOutputs_ReturnsOnlyFormatsThatActuallyFailed()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            object plan = Activator.CreateInstance(GetNestedType("DeliverablePlan"));
            SetField(plan, "FileString", "PN-100");
            string root = CreateTempRoot();

            try
            {
                Directory.CreateDirectory(Path.Combine(root, "step"));
                File.WriteAllText(Path.Combine(root, "step", "PN-100.step"), new string('X', 1024));

                object[] args = { plan, root, new[] { "step", "stl" }, null, null, null };
                bool valid = (bool)InvokePrivate(publisher, "ValidateRequestedOutputs", args);
                var failedFormats = (List<string>)args[4];

                Assert.IsFalse(valid);
                CollectionAssert.AreEqual(new[] { "stl" }, failedFormats);
                StringAssert.Contains((string)args[5], "stl=");
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void TryFinalizeExportedTempFile_OversizedMeshSkipsWithoutPromoting()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            SetPrivateField(publisher, "_activeMeshExportLimitBytes", 128L);
            string root = CreateTempRoot();
            string finalPath = Path.Combine(root, "final.stl");
            string tempPath = Path.Combine(root, "temp.stl");

            try
            {
                File.WriteAllText(tempPath, BuildAsciiStl() + new string(' ', 256), Encoding.ASCII);

                object result = InvokePrivate(publisher, "TryFinalizeExportedTempFile", "stl", tempPath, finalPath, null);

                Assert.AreEqual(false, GetField(result, "Success"));
                Assert.AreEqual(true, GetField(result, "Skipped"));
                StringAssert.Contains((string)GetField(result, "Reason"), "limit is");
                Assert.IsFalse(File.Exists(finalPath));
                Assert.IsFalse(File.Exists(tempPath));
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void TryFinalizeExportedTempFile_LogsFailureBeforeRemovingTempArtifact()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string finalPath = Path.Combine(root, "final.stl");
            string tempPath = Path.Combine(root, "failed.tmp.stl");
            var messages = new List<string>();

            try
            {
                File.WriteAllText(tempPath, "solid x\nendsolid x\n", Encoding.ASCII);

                object result = InvokePrivate(
                    publisher,
                    "TryFinalizeExportedTempFile",
                    "stl",
                    tempPath,
                    finalPath,
                    new Action<string>(messages.Add));

                Assert.AreEqual(false, GetField(result, "Success"));
                Assert.IsTrue(messages.Exists(message => message.StartsWith("OUTPUT failed:", StringComparison.Ordinal)));
                Assert.IsFalse(File.Exists(tempPath));
                Assert.IsFalse(File.Exists(finalPath));
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void BuildSaveBeforeExportPromptMessage_ExplainsUnsavedAndModifiedCases()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());

            string unsaved = (string)InvokePrivate(publisher, "BuildSaveBeforeExportPromptMessage", "BOM export", "Part1.SLDPRT", "unsaved");
            string modified = (string)InvokePrivate(publisher, "BuildSaveBeforeExportPromptMessage", "batch export", "Asm1.SLDASM", "modified");

            StringAssert.Contains(unsaved, "\"Part1.SLDPRT\" must be saved before BOM export.");
            StringAssert.Contains(unsaved, "not been saved yet");
            StringAssert.Contains(modified, "\"Asm1.SLDASM\" must be saved before batch export.");
            StringAssert.Contains(modified, "unsaved changes");
        }

        [TestMethod]
        public void DeliverablesExportSession_RoundTripsPhysicalQueueAndStatus()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            var options = new PublishOptions
            {
                DeliverablesFolder = @"C:\out\deliverables",
                BomFolder = @"C:\out\bom",
                ExportStep = true,
                TopLevelOnly = false
            };

            Type queueItemType = GetNestedType("PhysicalExportQueueItem");
            Type listType = typeof(List<>).MakeGenericType(queueItemType);
            var queue = (IList)Activator.CreateInstance(listType);
            queue.Add(CreatePhysicalExportQueueItem(queueItemType, @"C:\vault\root.sldasm", false, "root", 0, true));
            queue.Add(CreatePhysicalExportQueueItem(queueItemType, @"C:\vault\root.slddrw", true, "root drawing", 0, true));

            object session = InvokePrivate(
                publisher,
                "CreateDeliverablesExportSessionState",
                queue,
                options,
                @"C:\vault\root.sldasm",
                "MAIN",
                string.Empty,
                @"C:\logs\export.log");

            Assert.AreEqual(3, GetField(session, "SchemaVersion"));

            IList sessionQueue = (IList)GetField(session, "PhysicalQueue");
            Assert.AreEqual(2, sessionQueue.Count);
            Assert.AreEqual("pending", GetField(sessionQueue[0], "Status"));
            SetField(sessionQueue[0], "Status", "done");
            SetField(sessionQueue[0], "CompletedUtc", "2026-07-05T00:00:00");

            string json = (string)InvokePrivate(publisher, "SerializeExportSession", session);
            Assert.IsFalse(string.IsNullOrWhiteSpace(json));

            object roundTrip = InvokePrivate(publisher, "DeserializeExportSession", json);
            Assert.IsNotNull(roundTrip);
            Assert.AreEqual(3, GetField(roundTrip, "SchemaVersion"));

            IList roundTripQueue = (IList)GetField(roundTrip, "PhysicalQueue");
            Assert.AreEqual(2, roundTripQueue.Count);
            Assert.AreEqual("done", GetField(roundTripQueue[0], "Status"));
            Assert.AreEqual("2026-07-05T00:00:00", GetField(roundTripQueue[0], "CompletedUtc"));
            Assert.AreEqual("pending", GetField(roundTripQueue[1], "Status"));
            Assert.AreEqual(true, GetField(roundTripQueue[1], "IsDrawing"));
        }

        [TestMethod]
        public void PhysicalExportQueue_OrdersModelImmediatelyBeforeItsDrawing()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            Type planType = GetNestedType("DeliverablePlan");
            object plan = Activator.CreateInstance(planType, true);
            SetField(plan, "ModelPath", @"C:\vault\PN-100.SLDPRT");
            SetField(plan, "DrawingPath", @"C:\vault\PN-100.SLDDRW");
            SetField(plan, "DrawingExists", true);
            SetField(plan, "ExportStep", true);
            SetField(plan, "ExportPdf", true);
            SetField(plan, "DocType", 1);

            IList manifest = (IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(planType));
            manifest.Add(plan);

            IList queue = (IList)InvokePrivate(publisher, "BuildPhysicalExportQueue", manifest, null);

            Assert.AreEqual(2, queue.Count);
            Assert.AreEqual(false, GetField(queue[0], "IsDrawing"));
            Assert.AreEqual(@"C:\vault\PN-100.SLDPRT", GetField(queue[0], "PhysicalPath"));
            Assert.AreEqual(true, GetField(queue[1], "IsDrawing"));
            Assert.AreEqual(@"C:\vault\PN-100.SLDDRW", GetField(queue[1], "PhysicalPath"));
        }

        [TestMethod]
        [DoNotParallelize]
        public void HasIncompleteExportSession_RejectsLegacySchemaVersion()
        {
            string appDataRoot = Path.Combine(Path.GetTempPath(), "tinymrp-test-appdata-" + Guid.NewGuid().ToString("N"));
            string originalAppData = Environment.GetEnvironmentVariable("APPDATA", EnvironmentVariableTarget.Process);

            try
            {
                Directory.CreateDirectory(appDataRoot);
                Environment.SetEnvironmentVariable("APPDATA", appDataRoot, EnvironmentVariableTarget.Process);

                var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
                string activePath = (string)InvokePrivate(publisher, "GetActiveExportSessionPath");
                Directory.CreateDirectory(Path.GetDirectoryName(activePath));

                // A schema-version-1 (legacy PlannedRef-based) session with no PhysicalQueue must never
                // be reported as resumable by the current (PhysicalExportQueueItem-based) pipeline.
                object legacySession = Activator.CreateInstance(GetNestedType("ExportSessionState"), true);
                SetField(legacySession, "SchemaVersion", 1);
                SetField(legacySession, "Status", "running");
                string legacyJson = (string)InvokePrivate(publisher, "SerializeExportSession", legacySession);
                File.WriteAllText(activePath, legacyJson, new UTF8Encoding(false));

                Assert.IsFalse(publisher.HasIncompleteExportSession());
            }
            finally
            {
                Environment.SetEnvironmentVariable("APPDATA", originalAppData, EnvironmentVariableTarget.Process);
                if (Directory.Exists(appDataRoot))
                {
                    Directory.Delete(appDataRoot, true);
                }
            }
        }

        [TestMethod]
        public void BuildBomTempAssemblyPath_UsesPrivateTempFolderAndSldasmName()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = (string)InvokePrivate(publisher, "GetBomTempRootDirectory");

            object[] args = { "unit_test_token", null };
            string tempAssemblyPath = (string)InvokePrivate(publisher, "BuildBomTempAssemblyPath", args);
            string tempDirectory = args[1] as string;

            Assert.IsFalse(string.IsNullOrWhiteSpace(root));
            Assert.AreEqual(Path.Combine(root, "unit_test_token"), tempDirectory);
            Assert.AreEqual(Path.Combine(tempDirectory, "tinymrp_treebom_unit_test_token.SLDASM"), tempAssemblyPath);
        }

        [TestMethod]
        public void IsPathUnderDirectory_AcceptsNestedPathAndRejectsSibling()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = Path.Combine(Path.GetTempPath(), "TinyMRP", "bom-temp");
            string nested = Path.Combine(root, "abc", "file.sldasm");
            string sibling = Path.Combine(Path.GetTempPath(), "TinyMRP", "bom-temp-other", "file.sldasm");

            bool nestedResult = (bool)InvokePrivate(publisher, "IsPathUnderDirectory", nested, root);
            bool siblingResult = (bool)InvokePrivate(publisher, "IsPathUnderDirectory", sibling, root);

            Assert.IsTrue(nestedResult);
            Assert.IsFalse(siblingResult);
        }

        [TestMethod]
        public void TreeBomTempAssemblyBuilder_DoesNotSaveTempAssembly()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);
            int start = source.IndexOf("private bool TryBuildBomWithUnsavedTempAssembly", StringComparison.Ordinal);
            int end = source.IndexOf("private int SafeTableRowCount", StringComparison.Ordinal);

            Assert.IsTrue(start >= 0);
            Assert.IsTrue(end > start);

            string methodBody = source.Substring(start, end - start);
            StringAssert.Contains(methodBody, "SaveAsText");
            StringAssert.Contains(methodBody, "CloseTempAssemblyNoSaveNoPrompt");
            Assert.IsTrue(methodBody.IndexOf("TrySilentSaveAs", StringComparison.Ordinal) < 0);
            Assert.IsTrue(methodBody.IndexOf("TrySilentSaveCurrent", StringComparison.Ordinal) < 0);
            Assert.IsTrue(methodBody.IndexOf("Save3(", StringComparison.Ordinal) < 0);
        }

        [TestMethod]
        public void ForceCloseDocNoSave_UsesCloseDocWithoutQuitDocCalls()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);
            int start = source.IndexOf("private void ForceCloseDocNoSave", StringComparison.Ordinal);
            int end = source.IndexOf("private void CloseNonRootDocs", StringComparison.Ordinal);

            Assert.IsTrue(start >= 0);
            Assert.IsTrue(end > start);

            string methodBody = source.Substring(start, end - start);
            // CloseDoc never prompts to save; QuitDoc and ActivateDoc-before-close are forbidden here
            // (activating hidden reference docs to close them is what hung large-assembly exports).
            Assert.IsTrue(methodBody.IndexOf("CloseDoc(", StringComparison.Ordinal) >= 0);
            Assert.IsTrue(methodBody.IndexOf("_swApp.QuitDoc(", StringComparison.Ordinal) < 0);
            Assert.IsTrue(methodBody.IndexOf("ActivateDoc", StringComparison.Ordinal) < 0);
            Assert.IsTrue(methodBody.IndexOf("Thread.Sleep", StringComparison.Ordinal) < 0);
        }

        [TestMethod]
        public void CloseTempAssemblyNoSaveNoPrompt_UsesCloseDocWithoutQuitDocCalls()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);
            int start = source.IndexOf("private bool CloseTempAssemblyNoSaveNoPrompt", StringComparison.Ordinal);
            int end = source.IndexOf("private bool TryDeleteTempBomDirectory", StringComparison.Ordinal);

            Assert.IsTrue(start >= 0);
            Assert.IsTrue(end > start);

            string methodBody = source.Substring(start, end - start);
            // The temp assembly close delegates to ForceCloseDocNoSave (no-save, no-prompt) and never QuitDoc.
            Assert.IsTrue(methodBody.IndexOf("ForceCloseDocNoSave(", StringComparison.Ordinal) >= 0);
            Assert.IsTrue(methodBody.IndexOf("_swApp.QuitDoc(", StringComparison.Ordinal) < 0);
        }

        [TestMethod]
        public void DrawingDiscovery_RemainsPartNumberSlddrwConvention()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);

            // Drawings are discovered next to the model as "<partNumber>.SLDDRW" during manifest
            // planning; the drawing export receives that resolved path and must not re-derive it.
            Assert.IsTrue(source.IndexOf("? OnlyFolder(modelPath) + partNumber + \".SLDDRW\"", StringComparison.Ordinal) >= 0);
            Assert.IsTrue(source.IndexOf("candidateDrawing", StringComparison.OrdinalIgnoreCase) < 0);
            Assert.IsTrue(source.IndexOf("fallback drawing", StringComparison.OrdinalIgnoreCase) < 0);
        }

        [TestMethod]
        public void ExportTraversal_UsesCapturedRootAndExclusionAwareTreePlanning()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);
            string traverse = GetMethodSource(source, "private string TraverseModel", "private void CreateUploadPack");
            string uploadPack = GetMethodSource(source, "private void CreateUploadPack", "private AssociatedFilesPayload ReadAssociatedFiles");
            string planning = GetMethodSource(source, "private List<PlannedRef> PlanRefsForDeliverables", "private void UpdatePlannedRefsFromTree");

            Assert.IsTrue(traverse.IndexOf("rootModel", StringComparison.Ordinal) >= 0);
            Assert.IsTrue(traverse.IndexOf("_swApp.ActiveDoc", StringComparison.Ordinal) < 0);
            Assert.IsTrue(uploadPack.IndexOf("_swApp.ActiveDoc", StringComparison.Ordinal) < 0);
            Assert.IsTrue(planning.IndexOf("GetComponents(", StringComparison.Ordinal) < 0);
        }

        [TestMethod]
        public void DrawingQueue_HasSingleDocumentOwnerWithoutRedundantOpenTracker()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);
            string queueRunner = GetMethodSource(
                source,
                "private void RunPhysicalDrawingQueueItem",
                "private void RunPhysicalExportQueue");

            Assert.IsTrue(queueRunner.IndexOf("OpenDocReadOnlySilent", StringComparison.Ordinal) >= 0);
            Assert.IsTrue(queueRunner.IndexOf("ForceCloseDocNoSave", StringComparison.Ordinal) >= 0);
            Assert.IsTrue(source.IndexOf("class OpenTracker", StringComparison.Ordinal) < 0);
        }

        [TestMethod]
        public void CompletionPopup_RestoresInitiatingDocumentBeforeShowingMessage()
        {
            string source = File.ReadAllText(GetMainPaneSourcePath(), Encoding.UTF8);
            string completion = GetMethodSource(
                source,
                "private void ShowExportFinished",
                "private void OnCancelCurrentTask");

            int activation = completion.IndexOf("ActivateDoc3", StringComparison.Ordinal);
            int recovery = completion.IndexOf("EnsureSolidWorksReady", StringComparison.Ordinal);
            int popup = completion.IndexOf("ShowExportCompletion", StringComparison.Ordinal);
            int finalRecovery = completion.IndexOf("EnsureSolidWorksReady();", popup, StringComparison.Ordinal);
            Assert.IsTrue(activation >= 0);
            Assert.IsTrue(recovery > activation);
            Assert.IsTrue(popup > recovery);
            Assert.IsTrue(finalRecovery > popup);
            StringAssert.Contains(source, "ShowExportFinished(\"File export\", initiatingDocumentTitle)");
            StringAssert.Contains(source, "ShowExportFinished(\"Upload pack\", initiatingDocumentTitle)");
            StringAssert.Contains(source, "ShowExportFinished(\"BOM export\", initiatingDocumentTitle)");
            StringAssert.Contains(source, "logLink.Links.Add(0, logLink.Text.Length, path)");
            StringAssert.Contains(source, "_actionStatusLabel.Links.Add(start, path.Length, path)");
        }

        [TestMethod]
        public void ExportCleanup_DoesNotEnterGlobalAutomationModeAndReenablesFileMenu()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);
            string recovery = GetMethodSource(
                source,
                "private void RestoreSolidWorksInteraction",
                "public void EnsureSolidWorksReady");

            Assert.IsTrue(source.IndexOf("CommandInProgress = true", StringComparison.Ordinal) < 0);
            Assert.IsTrue(source.IndexOf("UserControl = false", StringComparison.Ordinal) < 0);
            Assert.IsTrue(source.IndexOf("UserControlBackground = true", StringComparison.Ordinal) < 0);
            StringAssert.Contains(recovery, "UserControlBackground = false");
            StringAssert.Contains(recovery, "UserControl = true");
            StringAssert.Contains(recovery, "CommandInProgress = false");
            StringAssert.Contains(recovery, "EnableFileMenu = true");
        }

        [TestMethod]
        public void NumberingStartup_LoadsSchemeCacheAndLastUsedDoesNotCallPreview()
        {
            string source = File.ReadAllText(GetMainPaneSourcePath(), Encoding.UTF8);
            string startup = GetMethodSource(source, "private async void OnPaneLoaded", "private NumberingApiClient GetNumberingClient");
            string lastUsed = GetMethodSource(source, "private void RefreshLastUsedPartNumber", "private void SetLastUsedPartNumber");

            StringAssert.Contains(startup, "RefreshSchemes(true)");
            StringAssert.Contains(startup, "Task.Run");
            StringAssert.Contains(startup, "Connected to the TinyMRP server");
            StringAssert.Contains(startup, "backend does not provide latest part numbers");
            StringAssert.Contains(lastUsed, "scheme.LastPartNumber");
            Assert.IsTrue(lastUsed.IndexOf("client.Preview", StringComparison.Ordinal) < 0);
        }

        [TestMethod]
        public void AddinSource_HasNoSolidWorksCustomPropertyMutationCalls()
        {
            string servicesDirectory = Path.GetDirectoryName(GetPublisherSourcePath());
            string projectDirectory = Directory.GetParent(servicesDirectory).FullName;
            foreach (string path in Directory.GetFiles(projectDirectory, "*.cs", SearchOption.AllDirectories))
            {
                string source = File.ReadAllText(path, Encoding.UTF8);
                Assert.IsTrue(source.IndexOf(".Set2(", StringComparison.Ordinal) < 0, path);
                Assert.IsTrue(source.IndexOf(".Add3(", StringComparison.Ordinal) < 0, path);
            }
        }

        private static object InvokePrivate(object target, string methodName, params object[] args)
        {
            MethodInfo method = target.GetType().GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Instance);
            Assert.IsNotNull(method);
            return method.Invoke(target, args);
        }

        private static bool InvokePrivateWithOutString(object target, string methodName, string path, out string reason)
        {
            object[] args = { path, null, null };
            bool result = (bool)InvokePrivate(target, methodName, args);
            reason = args[2] as string ?? string.Empty;
            return result;
        }

        private static bool InvokePrivateValidateExportedOutput(object target, string type, string path, out string reason)
        {
            object[] args = { type, path, null, null };
            bool result = (bool)InvokePrivate(target, "ValidateExportedOutput", args);
            reason = args[3] as string ?? string.Empty;
            return result;
        }

        private static Type GetNestedType(string nestedTypeName)
        {
            Type nestedType = typeof(TinyMrpPublisher).GetNestedType(nestedTypeName, BindingFlags.NonPublic);
            Assert.IsNotNull(nestedType);
            return nestedType;
        }

        private static object CreatePhysicalExportQueueItem(Type queueItemType, string physicalPath, bool isDrawing,
            string displayName, int docType, bool isRoot)
        {
            object entry = Activator.CreateInstance(queueItemType, true);
            SetField(entry, "IsDrawing", isDrawing);
            SetField(entry, "PhysicalPath", physicalPath);
            SetField(entry, "DisplayName", displayName);
            SetField(entry, "DocType", docType);
            SetField(entry, "IsRoot", isRoot);
            return entry;
        }

        private static object GetField(object target, string fieldName)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Public | BindingFlags.Instance);
            Assert.IsNotNull(field);
            return field.GetValue(target);
        }

        private static void SetField(object target, string fieldName, object value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Public | BindingFlags.Instance);
            Assert.IsNotNull(field);
            field.SetValue(target, value);
        }

        private static string GetMethodSource(string source, string startMarker, string endMarker)
        {
            int start = source.IndexOf(startMarker, StringComparison.Ordinal);
            int end = source.IndexOf(endMarker, start + startMarker.Length, StringComparison.Ordinal);
            Assert.IsTrue(start >= 0, startMarker);
            Assert.IsTrue(end > start, endMarker);
            return source.Substring(start, end - start);
        }

        private static void SetPrivateField(object target, string fieldName, object value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.NonPublic | BindingFlags.Instance);
            Assert.IsNotNull(field);
            field.SetValue(target, value);
        }

        private static string GetPublisherSourcePath()
        {
            string current = AppDomain.CurrentDomain.BaseDirectory;
            for (int i = 0; i < 8; i++)
            {
                string candidate = Path.Combine(current, "TinyMRP.SolidWorksAddin", "Services", "TinyMrpPublisher.cs");
                if (File.Exists(candidate))
                {
                    return candidate;
                }

                current = Path.GetFullPath(Path.Combine(current, ".."));
            }

            Assert.Fail("Could not locate TinyMrpPublisher.cs from test output directory.");
            return string.Empty;
        }

        private static string GetMainPaneSourcePath()
        {
            string servicesDirectory = Path.GetDirectoryName(GetPublisherSourcePath());
            string path = Path.GetFullPath(Path.Combine(servicesDirectory, "..", "UI", "MainPaneControl.cs"));
            Assert.IsTrue(File.Exists(path));
            return path;
        }

        private static string CreateTempRoot()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_test_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            return root;
        }

        private static void DeleteDirectoryIfExists(string path)
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, true);
            }
        }

        private static string BuildAsciiStl()
        {
            return string.Join("\n", new[]
            {
                "solid test",
                "  facet normal 0 0 1",
                "    outer loop",
                "      vertex 0 0 0",
                "      vertex 1 0 0",
                "      vertex 0 1 0",
                "    endloop",
                "  endfacet",
                "endsolid test",
                string.Empty
            });
        }

        private static string BuildHeaderOnlyPly(int vertexCount)
        {
            return string.Join("\n", new[]
            {
                "ply",
                "format ascii 1.0",
                "comment header-only test file",
                "element vertex " + vertexCount,
                "property float x",
                "property float y",
                "property float z",
                "element face 1",
                "property list uchar int vertex_indices",
                "end_header",
                string.Empty
            });
        }

        private static string BuildValidAsciiPly()
        {
            string ply = string.Join("\n", new[]
            {
                "ply",
                "format ascii 1.0",
                "comment padded test file for minimum byte validation",
                "comment another line to keep the sample above the mesh threshold",
                "element vertex 3",
                "property float x",
                "property float y",
                "property float z",
                "element face 1",
                "property list uchar int vertex_indices",
                "end_header",
                "0 0 0",
                "1 0 0",
                "0 1 0",
                "3 0 1 2",
                string.Empty
            });

            if (Encoding.ASCII.GetByteCount(ply) < 160)
            {
                ply += new string(' ', 160 - Encoding.ASCII.GetByteCount(ply));
            }

            return ply;
        }
    }
}
