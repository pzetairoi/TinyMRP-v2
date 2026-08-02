using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Web.Script.Serialization;
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
                Files = new List<AssociatedFileEntry>
                {
                    new AssociatedFileEntry { Path = @"C:\temp\scan.e57", Label = "scan" }
                }
            };

            string json = payload.ToJson();
            var loaded = AssociatedFilesPayload.FromJson(json);

            Assert.IsFalse(json.Contains("\"pn\""));
            Assert.IsFalse(json.Contains("\"rev\""));
            Assert.AreEqual("", loaded.PartNumber);
            Assert.AreEqual("", loaded.Revision);
            Assert.AreEqual(1, loaded.Files.Count);
            Assert.AreEqual(@"C:\temp\scan.e57", loaded.Files[0].Path);
            Assert.AreEqual("scan", loaded.Files[0].Label);
        }

        [TestMethod]
        public void AssociatedFilesPayload_ParsesWrappedJson()
        {
            string json = "{\"pn\":\"PN-20\",\"rev\":\"B\",\"files\":[{\"path\":\"C:\\\\temp\\\\report.pdf\",\"label\":\"report\"}]}";
            var serializer = new JavaScriptSerializer();
            string wrapped = serializer.Serialize(json);

            var loaded = AssociatedFilesPayload.FromJson(wrapped);

            Assert.AreEqual("PN-20", loaded.PartNumber);
            Assert.AreEqual("B", loaded.Revision);
            Assert.AreEqual(1, loaded.Files.Count);
            Assert.AreEqual(@"C:\temp\report.pdf", loaded.Files[0].Path);
            Assert.AreEqual("report", loaded.Files[0].Label);
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
            var extras = new List<UploadPackBuilder.AssociatedFilesBundle>
            {
                new UploadPackBuilder.AssociatedFilesBundle
                {
                    PartNumber = "PN-10",
                    Revision = "",
                    Files = new List<AssociatedFileEntry>
                    {
                        new AssociatedFileEntry { Path = assocPath, Label = "scan" }
                    }
                }
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
            var extras = new List<UploadPackBuilder.AssociatedFilesBundle>
            {
                new UploadPackBuilder.AssociatedFilesBundle
                {
                    PartNumber = "PN-11",
                    Revision = "A",
                    Files = new List<AssociatedFileEntry>
                    {
                        new AssociatedFileEntry { Path = Path.Combine(root, "missing.dat"), Label = "missing" }
                    }
                }
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

        [TestMethod]
        public void UploadPackBuilder_ExcludesTransientAndFailedDeliverables()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_pack_" + Guid.NewGuid().ToString("N"));
            string deliverables = Path.Combine(root, "deliverables");
            string stlDir = Path.Combine(deliverables, "stl");
            Directory.CreateDirectory(stlDir);

            File.WriteAllText(Path.Combine(stlDir, "PN-12_REV_A.stl"), "valid");
            File.WriteAllText(Path.Combine(stlDir, "PN-12_REV_A_123.tmp.stl"), "failed temp");
            File.WriteAllText(Path.Combine(stlDir, "PN-12_REV_A.stl.bad"), "failed output");
            File.WriteAllText(Path.Combine(stlDir, "PN-12_REV_A.stl.replacebak"), "replacement backup");

            string zipPath = Path.Combine(root, "pack.zip");
            UploadPackBuilder.Build(
                zipPath,
                deliverables,
                string.Empty,
                string.Empty,
                null,
                null,
                new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "PN-12_REV_A" },
                new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "stl" });

            using (var zip = ZipFile.OpenRead(zipPath))
            {
                Assert.IsNotNull(zip.GetEntry("deliverables/stl/PN-12_REV_A.stl"));
                Assert.IsNull(zip.GetEntry("deliverables/stl/PN-12_REV_A_123.tmp.stl"));
                Assert.IsNull(zip.GetEntry("deliverables/stl/PN-12_REV_A.stl.bad"));
                Assert.IsNull(zip.GetEntry("deliverables/stl/PN-12_REV_A.stl.replacebak"));
            }

            Directory.Delete(root, true);
        }

        [TestMethod]
        public void TextFileHelper_WritesUtf8NoBom()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_text_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            string path = Path.Combine(root, "flatbom.txt");

            TextFileHelper.WriteAllTextUtf8NoBom(path, "{'partnumber':'PN'}");

            byte[] bytes = File.ReadAllBytes(path);
            Assert.IsFalse(bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF);
            Assert.AreEqual((byte)'{', bytes[0]);

            Directory.Delete(root, true);
        }

        [TestMethod]
        public void TextFileHelper_StripsUtf8Bom()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp_text_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            string path = Path.Combine(root, "treebom.txt");

            byte[] payload = new byte[] { 0xEF, 0xBB, 0xBF, (byte)'I', (byte)'T', (byte)'E', (byte)'M' };
            File.WriteAllBytes(path, payload);
            Assert.IsTrue(TextFileHelper.HasUtf8Bom(path));

            bool stripped = TextFileHelper.StripUtf8Bom(path);
            Assert.IsTrue(stripped);
            Assert.IsFalse(TextFileHelper.HasUtf8Bom(path));

            byte[] bytes = File.ReadAllBytes(path);
            Assert.AreEqual((byte)'I', bytes[0]);

            Directory.Delete(root, true);
        }
    }
}
