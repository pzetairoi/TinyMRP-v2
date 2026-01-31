using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class AssociatedFilesTests
    {
        [TestMethod]
        public void AssociatedFilesPayload_RoundTrip()
        {
            var payload = new AssociatedFilesPayload
            {
                PartNumber = "PN-10",
                Revision = "",
                Files = new List<AssociatedFileEntry>
                {
                    new AssociatedFileEntry { Path = @"C:\temp\scan.e57", Label = "scan" }
                }
            };

            string json = payload.ToJson();
            var loaded = AssociatedFilesPayload.FromJson(json);

            Assert.AreEqual("PN-10", loaded.PartNumber);
            Assert.AreEqual("", loaded.Revision);
            Assert.AreEqual(1, loaded.Files.Count);
            Assert.AreEqual(@"C:\temp\scan.e57", loaded.Files[0].Path);
            Assert.AreEqual("scan", loaded.Files[0].Label);
        }

        [TestMethod]
        public void UploadPackBuilder_CreatesExpectedEntries()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_pack_" + Guid.NewGuid().ToString("N"));
            string deliverables = Path.Combine(root, "deliverables");
            string pdfDir = Path.Combine(deliverables, "pdf");
            string bomDir = Path.Combine(deliverables, "bom");
            string assocDir = Path.Combine(root, "assoc");
            Directory.CreateDirectory(pdfDir);
            Directory.CreateDirectory(bomDir);
            Directory.CreateDirectory(assocDir);

            string pdfPath = Path.Combine(pdfDir, "PN-10_REV_.pdf");
            File.WriteAllText(pdfPath, "pdf");
            string otherPdfPath = Path.Combine(pdfDir, "PN-99_REV_A.pdf");
            File.WriteAllText(otherPdfPath, "other");
            string flat = Path.Combine(bomDir, "PN-10_REV__FLATBOM.txt");
            string tree = Path.Combine(bomDir, "PN-10_REV__TREEBOM.txt");
            File.WriteAllText(flat, "flat");
            File.WriteAllText(tree, "tree");

            string assocPath = Path.Combine(assocDir, "scan.e57");
            File.WriteAllText(assocPath, "scan");

            string zipPath = Path.Combine(root, "pack.zip");
            var extras = new List<AssociatedFileEntry>
            {
                new AssociatedFileEntry { Path = assocPath, Label = "scan" }
            };
            var allowedBases = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "PN-10_REV_"
            };
            var allowedGroups = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "pdf"
            };

            UploadPackBuilder.Build(
                zipPath,
                deliverables,
                flat,
                tree,
                "PN-10",
                "",
                extras,
                null,
                allowedBases,
                allowedGroups);

            using (var zip = ZipFile.OpenRead(zipPath))
            {
                Assert.IsNotNull(zip.GetEntry("bom/PN-10_REV__FLATBOM.txt"));
                Assert.IsNotNull(zip.GetEntry("bom/PN-10_REV__TREEBOM.txt"));
                Assert.IsNotNull(zip.GetEntry("deliverables/pdf/PN-10_REV_.pdf"));
                Assert.IsNull(zip.GetEntry("deliverables/pdf/PN-99_REV_A.pdf"));
                Assert.IsNotNull(zip.GetEntry("extra/PN-10/__no_rev__/scan.e57"));
            }

            Directory.Delete(root, true);
        }

        [TestMethod]
        public void UploadPackBuilder_SkipsMissingExtraFiles()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_pack_" + Guid.NewGuid().ToString("N"));
            string deliverables = Path.Combine(root, "deliverables");
            Directory.CreateDirectory(deliverables);

            string zipPath = Path.Combine(root, "pack.zip");
            var extras = new List<AssociatedFileEntry>
            {
                new AssociatedFileEntry { Path = Path.Combine(root, "missing.dat"), Label = "missing" }
            };
            var allowedBases = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "PN-11_REV_A"
            };
            var allowedGroups = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "pdf"
            };

            UploadPackBuilder.Build(
                zipPath,
                deliverables,
                string.Empty,
                string.Empty,
                "PN-11",
                "A",
                extras,
                null,
                allowedBases,
                allowedGroups);

            using (var zip = ZipFile.OpenRead(zipPath))
            {
                Assert.IsNull(zip.GetEntry("extra/PN-11/A/missing.dat"));
            }

            Directory.Delete(root, true);
        }
    }
}
