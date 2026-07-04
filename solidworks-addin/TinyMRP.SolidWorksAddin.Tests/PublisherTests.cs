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
        public void BuildTopLevelOnlyDeliverablesQueue_CreatesSingleRootEntry()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());

            object queueObj = InvokePrivate(
                publisher,
                "BuildTopLevelOnlyDeliverablesQueue",
                @"C:\vault\root.sldasm",
                "MAIN",
                true);

            var queue = queueObj as IList;
            Assert.IsNotNull(queue);
            Assert.AreEqual(1, queue.Count);

            object entry = queue[0];
            Assert.AreEqual(@"C:\vault\root.sldasm", GetField(entry, "ModelPath"));
            Assert.AreEqual("MAIN", GetField(entry, "ConfigurationName"));
            Assert.AreEqual(true, GetField(entry, "IsAssembly"));
            Assert.AreEqual(0, GetField(entry, "MaxDepth"));
            Assert.AreEqual(0, GetField(entry, "SubtreeEstimate"));
            Assert.AreEqual(true, GetField(entry, "IsRoot"));
        }

        [TestMethod]
        public void SortDeliverablesQueue_OrdersPartsBeforeAssembliesAndRootLast()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            Type plannedRefType = GetPlannedRefType();
            Type listType = typeof(List<>).MakeGenericType(plannedRefType);
            var queue = (IList)Activator.CreateInstance(listType);

            queue.Add(CreatePlannedRef(plannedRefType, @"C:\vault\z_part.sldprt", "B", false, 3, 0, false));
            queue.Add(CreatePlannedRef(plannedRefType, @"C:\vault\a_part.sldprt", "A", false, 3, 0, false));
            queue.Add(CreatePlannedRef(plannedRefType, @"C:\vault\subassy.sldasm", "SUB", true, 4, 2, false));
            queue.Add(CreatePlannedRef(plannedRefType, @"C:\vault\root.sldasm", "ROOT", true, 0, 6, true));

            InvokePrivate(publisher, "SortDeliverablesQueue", queue);

            Assert.AreEqual(@"C:\vault\a_part.sldprt", GetField(queue[0], "ModelPath"));
            Assert.AreEqual(@"C:\vault\z_part.sldprt", GetField(queue[1], "ModelPath"));
            Assert.AreEqual(@"C:\vault\subassy.sldasm", GetField(queue[2], "ModelPath"));
            Assert.AreEqual(@"C:\vault\root.sldasm", GetField(queue[3], "ModelPath"));
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
            string root = CreateTempRoot();
            string finalPath = Path.Combine(root, "valid.stl");

            try
            {
                File.WriteAllText(finalPath, BuildAsciiStl() + new string(' ', 256), Encoding.ASCII);

                object[] args = { "stl", finalPath, false, null, null, false, null, null };
                bool ok = (bool)InvokePrivate(publisher, "TryPrepareExportOutput", args);

                Assert.IsTrue(ok);
                Assert.AreEqual(true, args[5]);
                Assert.AreEqual("existing valid output", args[6]);
                Assert.AreEqual(string.Empty, args[4] as string ?? string.Empty);
                Assert.AreEqual(string.Empty, args[7] as string ?? string.Empty);
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
        public void ExportSessionSerialization_RoundTripsQueueOptionsAndOutputs()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            var options = new PublishOptions
            {
                DeliverablesFolder = @"C:\out\deliverables",
                BomFolder = @"C:\out\bom",
                ExportPly = true,
                ExportStl = true,
                OverwriteFiles = true,
                TopLevelOnly = true
            };

            Type plannedRefType = GetPlannedRefType();
            Type listType = typeof(List<>).MakeGenericType(plannedRefType);
            var queue = (IList)Activator.CreateInstance(listType);
            queue.Add(CreatePlannedRef(plannedRefType, @"C:\vault\root.sldasm", "MAIN", true, 0, 4, true));
            queue.Add(CreatePlannedRef(plannedRefType, @"C:\vault\part.sldprt", "DEFAULT", false, 2, 0, false));

            object session = InvokePrivate(
                publisher,
                "CreateExportSessionState",
                queue,
                options,
                @"C:\vault\root.sldasm",
                "MAIN",
                @"C:\plans\plan.txt",
                @"C:\logs\export.log");

            IList sessionQueue = (IList)GetField(session, "Queue");
            object firstItem = sessionQueue[0];
            SetField(firstItem, "Status", "done");
            SetField(firstItem, "Attempts", 2);
            SetField(firstItem, "PlyValidationReason", "replaced stale file");
            IList outputs = (IList)GetField(firstItem, "Outputs");
            outputs.Add(CreateExportedOutput("ply", @"C:\out\deliverables\ply\root.ply", 2048, true, string.Empty));

            string json = (string)InvokePrivate(publisher, "SerializeExportSession", session);
            Assert.IsFalse(string.IsNullOrWhiteSpace(json));

            object roundTrip = InvokePrivate(publisher, "DeserializeExportSession", json);
            Assert.IsNotNull(roundTrip);
            Assert.AreEqual(@"C:\vault\root.sldasm", GetField(roundTrip, "RootModelPath"));
            Assert.AreEqual("MAIN", GetField(roundTrip, "RootConfigurationName"));
            Assert.AreEqual(@"C:\plans\plan.txt", GetField(roundTrip, "PlanPath"));
            Assert.AreEqual(@"C:\logs\export.log", GetField(roundTrip, "LogPath"));

            var roundTripOptions = (PublishOptions)GetField(roundTrip, "Options");
            Assert.IsNotNull(roundTripOptions);
            Assert.AreEqual(@"C:\out\deliverables", roundTripOptions.DeliverablesFolder);
            Assert.IsTrue(roundTripOptions.ExportPly);
            Assert.IsTrue(roundTripOptions.ExportStl);
            Assert.IsTrue(roundTripOptions.OverwriteFiles);
            Assert.IsTrue(roundTripOptions.TopLevelOnly);

            IList roundTripQueue = (IList)GetField(roundTrip, "Queue");
            Assert.AreEqual(2, roundTripQueue.Count);
            Assert.AreEqual("done", GetField(roundTripQueue[0], "Status"));
            Assert.AreEqual(2, GetField(roundTripQueue[0], "Attempts"));
            IList roundTripOutputs = (IList)GetField(roundTripQueue[0], "Outputs");
            Assert.AreEqual(1, roundTripOutputs.Count);
            Assert.AreEqual("ply", GetField(roundTripOutputs[0], "Type"));
            Assert.AreEqual(2048L, GetField(roundTripOutputs[0], "Bytes"));
            Assert.AreEqual(true, GetField(roundTripOutputs[0], "Validated"));
        }

        [TestMethod]
        public void PrepareSessionForResume_RevalidatesRunningDoneAndFailedItems()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string validPlyPath = Path.Combine(root, "done_valid.ply");
            string invalidPlyPath = Path.Combine(root, "running_invalid.ply");

            try
            {
                File.WriteAllText(validPlyPath, BuildValidAsciiPly(), Encoding.ASCII);
                File.WriteAllText(invalidPlyPath, BuildHeaderOnlyPly(3), Encoding.ASCII);

                object session = CreateExportSession("running");
                IList queue = (IList)GetField(session, "Queue");
                queue.Add(CreateExportSessionItem(@"C:\vault\done.sldprt", "A", "done",
                    CreateExportedOutput("ply", validPlyPath, 0, false, string.Empty)));
                queue.Add(CreateExportSessionItem(@"C:\vault\running.sldprt", "B", "running",
                    CreateExportedOutput("ply", invalidPlyPath, 0, false, string.Empty)));
                queue.Add(CreateExportSessionItem(@"C:\vault\failed.sldprt", "C", "failed",
                    CreateExportedOutput("ply", invalidPlyPath, 0, false, string.Empty)));

                InvokePrivate(publisher, "PrepareSessionForResume", session, null);

                Assert.AreEqual("crashed_or_incomplete", GetField(session, "Status"));
                Assert.AreEqual("done", GetField(queue[0], "Status"));
                Assert.AreEqual(string.Empty, GetField(queue[0], "LastError"));
                Assert.AreEqual("pending", GetField(queue[1], "Status"));
                Assert.AreEqual("ply:header-only file", GetField(queue[1], "LastError"));
                Assert.AreEqual("header-only file", GetField(queue[1], "PlyValidationReason"));
                Assert.AreEqual("pending", GetField(queue[2], "Status"));
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void PrepareSessionForResume_ExpectedOutputsControlCompleteness_NotOnlyValidatedOutputs()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string validPlyPath = Path.Combine(root, "resume_valid.ply");
            string missingStepPath = Path.Combine(root, "resume_missing.step");

            try
            {
                File.WriteAllText(validPlyPath, BuildValidAsciiPly(), Encoding.ASCII);

                object session = CreateExportSession("paused");
                IList queue = (IList)GetField(session, "Queue");
                object item = CreateExportSessionItem(@"C:\vault\partial.sldprt", "A", "done",
                    CreateExportedOutput("ply", validPlyPath, 0, true, string.Empty));

                IList expected = (IList)GetField(item, "ExpectedOutputs");
                expected.Add(CreateExportedOutput("ply", validPlyPath, 0, true, string.Empty));
                expected.Add(CreateExportedOutput("step", missingStepPath, 0, false, string.Empty));
                queue.Add(item);

                InvokePrivate(publisher, "PrepareSessionForResume", session, null);
                IList pending = (IList)InvokePrivate(publisher, "BuildPendingResumeQueue", session, null);

                Assert.AreEqual("pending", GetField(queue[0], "Status"));
                Assert.AreEqual("step:missing file", GetField(queue[0], "LastError"));
                Assert.AreEqual(1, pending.Count);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void BuildPendingResumeQueue_ValidDoneItemIsExcludedEvenWhenOverwriteTrue()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string validPlyPath = Path.Combine(root, "done_valid_overwrite.ply");

            try
            {
                File.WriteAllText(validPlyPath, BuildValidAsciiPly(), Encoding.ASCII);

                object session = CreateExportSession("paused");
                var options = (PublishOptions)GetField(session, "Options");
                options.OverwriteFiles = true;

                IList queue = (IList)GetField(session, "Queue");
                queue.Add(CreateExportSessionItem(@"C:\vault\done.sldprt", "A", "done",
                    CreateExportedOutput("ply", validPlyPath, 0, false, string.Empty)));

                InvokePrivate(publisher, "PrepareSessionForResume", session, null);
                IList pending = (IList)InvokePrivate(publisher, "BuildPendingResumeQueue", session, null);

                Assert.AreEqual("done", GetField(queue[0], "Status"));
                Assert.AreEqual(0, pending.Count);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void BuildPendingResumeQueue_DoneItemWithMissingOutput_IsIncluded()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            object session = CreateExportSession("paused");
            IList queue = (IList)GetField(session, "Queue");
            queue.Add(CreateExportSessionItem(@"C:\vault\missing.sldprt", "A", "done",
                CreateExportedOutput("ply", @"C:\does-not-exist\missing.ply", 0, false, string.Empty)));

            InvokePrivate(publisher, "PrepareSessionForResume", session, null);
            IList pending = (IList)InvokePrivate(publisher, "BuildPendingResumeQueue", session, null);

            Assert.AreEqual("pending", GetField(queue[0], "Status"));
            Assert.AreEqual("ply:missing file", GetField(queue[0], "LastError"));
            Assert.AreEqual(1, pending.Count);
            Assert.AreEqual(@"C:\vault\missing.sldprt", GetField(pending[0], "ModelPath"));
        }

        [TestMethod]
        public void BuildPendingResumeQueue_RunningItemWithValidOutputs_BecomesDoneAndIsExcluded()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string validPlyPath = Path.Combine(root, "running_valid.ply");

            try
            {
                File.WriteAllText(validPlyPath, BuildValidAsciiPly(), Encoding.ASCII);

                object session = CreateExportSession("running");
                IList queue = (IList)GetField(session, "Queue");
                queue.Add(CreateExportSessionItem(@"C:\vault\running-ok.sldprt", "A", "running",
                    CreateExportedOutput("ply", validPlyPath, 0, false, string.Empty)));

                InvokePrivate(publisher, "PrepareSessionForResume", session, null);
                IList pending = (IList)InvokePrivate(publisher, "BuildPendingResumeQueue", session, null);

                Assert.AreEqual("done", GetField(queue[0], "Status"));
                Assert.AreEqual(string.Empty, GetField(queue[0], "LastError"));
                Assert.AreEqual(0, pending.Count);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void BuildPendingResumeQueue_FailedAndUnknownStatuses_AreIncluded()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            string root = CreateTempRoot();
            string validPlyPath = Path.Combine(root, "unknown_valid.ply");

            try
            {
                File.WriteAllText(validPlyPath, BuildValidAsciiPly(), Encoding.ASCII);

                object session = CreateExportSession("failed");
                IList queue = (IList)GetField(session, "Queue");

                object failedItem = CreateExportSessionItem(@"C:\vault\failed.sldprt", "A", "failed",
                    CreateExportedOutput("ply", validPlyPath, 0, false, string.Empty));
                SetField(failedItem, "LastError", "previous export failed");
                queue.Add(failedItem);

                queue.Add(CreateExportSessionItem(@"C:\vault\unknown.sldprt", "B", "mystery",
                    CreateExportedOutput("ply", validPlyPath, 0, false, string.Empty)));

                InvokePrivate(publisher, "PrepareSessionForResume", session, null);
                IList pending = (IList)InvokePrivate(publisher, "BuildPendingResumeQueue", session, null);

                Assert.AreEqual("pending", GetField(queue[0], "Status"));
                Assert.AreEqual("pending", GetField(queue[1], "Status"));
                Assert.AreEqual(2, pending.Count);
            }
            finally
            {
                DeleteDirectoryIfExists(root);
            }
        }

        [TestMethod]
        public void PrepareSessionForResume_DurableSkippedItemRemainsSkippedAndCountsComplete()
        {
            var publisher = new TinyMrpPublisher(null, new TinyMrpConfig());
            object session = CreateExportSession("paused");
            IList queue = (IList)GetField(session, "Queue");

            object skippedItem = CreateExportSessionItem(@"C:\vault\skip.sldprt", "A", "skipped");
            SetField(skippedItem, "LastError", "no required outputs");
            queue.Add(skippedItem);

            InvokePrivate(publisher, "PrepareSessionForResume", session, null);
            IList pending = (IList)InvokePrivate(publisher, "BuildPendingResumeQueue", session, null);
            int completed = (int)InvokePrivate(publisher, "CountCompletedSessionItems", session);

            Assert.AreEqual("skipped", GetField(queue[0], "Status"));
            Assert.AreEqual(1, completed);
            Assert.AreEqual(0, pending.Count);
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
            int end = source.IndexOf("private bool TryBuildTreeBom", StringComparison.Ordinal);

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
        public void DrawingDiscovery_RemainsPartNumberSlddrwConvention()
        {
            string source = File.ReadAllText(GetPublisherSourcePath(), Encoding.UTF8);

            StringAssert.Contains(source, "string drawingPath = OnlyFolder(modelPath) + pn + \".SLDDRW\";");
            StringAssert.Contains(source, "string drawingPath = OnlyFolder(modelPath) + partNumber + \".SLDDRW\";");
            Assert.IsTrue(source.IndexOf("candidateDrawing", StringComparison.OrdinalIgnoreCase) < 0);
            Assert.IsTrue(source.IndexOf("fallback drawing", StringComparison.OrdinalIgnoreCase) < 0);
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

        private static Type GetPlannedRefType()
        {
            Type plannedRefType = typeof(TinyMrpPublisher).GetNestedType("PlannedRef", BindingFlags.NonPublic);
            Assert.IsNotNull(plannedRefType);
            return plannedRefType;
        }

        private static Type GetNestedType(string nestedTypeName)
        {
            Type nestedType = typeof(TinyMrpPublisher).GetNestedType(nestedTypeName, BindingFlags.NonPublic);
            Assert.IsNotNull(nestedType);
            return nestedType;
        }

        private static object CreatePlannedRef(Type plannedRefType, string modelPath, string configurationName, bool isAssembly,
            int maxDepth, int subtreeEstimate, bool isRoot)
        {
            object entry = Activator.CreateInstance(plannedRefType, true);
            SetField(entry, "ModelPath", modelPath);
            SetField(entry, "ConfigurationName", configurationName);
            SetField(entry, "IsAssembly", isAssembly);
            SetField(entry, "MaxDepth", maxDepth);
            SetField(entry, "SubtreeEstimate", subtreeEstimate);
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

        private static object CreateExportedOutput(string type, string path, long bytes, bool validated, string validationReason)
        {
            object output = Activator.CreateInstance(GetNestedType("ExportedOutputState"), true);
            SetField(output, "Type", type);
            SetField(output, "Path", path);
            SetField(output, "Bytes", bytes);
            SetField(output, "Validated", validated);
            SetField(output, "ValidationReason", validationReason);
            return output;
        }

        private static object CreateExportSessionItem(string modelPath, string configurationName, string status, params object[] outputs)
        {
            object item = Activator.CreateInstance(GetNestedType("ExportSessionItem"), true);
            SetField(item, "ItemId", modelPath + "|" + configurationName);
            SetField(item, "ModelPath", modelPath);
            SetField(item, "ConfigurationName", configurationName);
            SetField(item, "Status", status);

            IList outputList = (IList)GetField(item, "Outputs");
            foreach (object output in outputs)
            {
                outputList.Add(output);
            }

            return item;
        }

        private static object CreateExportSession(string status)
        {
            object session = Activator.CreateInstance(GetNestedType("ExportSessionState"), true);
            SetField(session, "SchemaVersion", 1);
            SetField(session, "SessionId", Guid.NewGuid().ToString("N"));
            SetField(session, "CreatedUtc", DateTime.UtcNow.ToString("s"));
            SetField(session, "UpdatedUtc", DateTime.UtcNow.ToString("s"));
            SetField(session, "Status", status);
            SetField(session, "RootModelPath", @"C:\vault\root.sldasm");
            SetField(session, "RootConfigurationName", "MAIN");
            SetField(session, "DeliverablesFolder", @"C:\out\deliverables");
            SetField(session, "BomFolder", @"C:\out\bom");
            SetField(session, "Options", new PublishOptions { ExportPly = true });
            return session;
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
