using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class ExportPolicyTests
    {
        [TestMethod]
        public void MeshExportLimit_AppliesOnlyToConfiguredMeshFormats()
        {
            long limit = MeshExportLimit.ToBytes(50);

            Assert.IsTrue(MeshExportLimit.IsOversized("ply", limit + 1, limit));
            Assert.IsTrue(MeshExportLimit.IsOversized("STL", limit + 1, limit));
            Assert.IsTrue(MeshExportLimit.IsOversized(".3mf", limit + 1, limit));
            Assert.IsFalse(MeshExportLimit.IsOversized("step", limit + 1, limit));
            Assert.IsFalse(MeshExportLimit.IsOversized("ply", limit, limit));
            Assert.AreEqual(50L * 1000 + 256L, MeshExportLimit.EstimateBytes("stl", 1000));
            Assert.AreEqual(49L * 1000 + 256L, MeshExportLimit.EstimateBytes("ply", 1000));
        }

        [TestMethod]
        public void AssociatedFilesStore_PersistsConfigurationsWithoutSolidWorksProperties()
        {
            string root = Path.Combine(Path.GetTempPath(), "tinymrp-associated-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            string modelPath = Path.Combine(root, "part.sldprt");
            File.WriteAllText(modelPath, string.Empty);

            try
            {
                var payload = new AssociatedFilesPayload
                {
                    Files = new List<AssociatedFileEntry>
                    {
                        new AssociatedFileEntry { Path = "certificate.pdf", Label = "Certificate" }
                    }
                };

                AssociatedFilesStore.Save(modelPath, "Default", payload);
                AssociatedFilesPayload loaded = AssociatedFilesStore.Load(modelPath, "Default", string.Empty);

                Assert.AreEqual(1, loaded.Files.Count);
                Assert.AreEqual("certificate.pdf", loaded.Files[0].Path);
                Assert.IsTrue(File.Exists(AssociatedFilesStore.GetSidecarPath(modelPath)));
            }
            finally
            {
                Directory.Delete(root, true);
            }
        }
    }
}
