using System;
using System.Collections.Generic;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class RenameHelperTests
    {
        [TestMethod]
        public void SanitizeFileName_RemovesInvalidCharacters()
        {
            string input = "A<>:\\\"/|?*B";
            string output = PartNumberRenameHelper.SanitizeFileName(input);
            Assert.IsFalse(output.Contains("<"));
            Assert.IsFalse(output.Contains(">"));
            Assert.IsFalse(output.Contains(":"));
            Assert.IsFalse(output.Contains("\\"));
            Assert.IsFalse(output.Contains("/"));
            Assert.IsFalse(output.Contains("|"));
            Assert.IsFalse(output.Contains("?"));
            Assert.IsFalse(output.Contains("*"));
            Assert.IsTrue(output.Contains("A"));
            Assert.IsTrue(output.Contains("B"));
        }

        [TestMethod]
        public void BuildBaseName_AppendsRevisionWhenRequested()
        {
            string output = PartNumberRenameHelper.BuildBaseName("PN-01", "A", true);
            Assert.AreEqual("PN-01-A", output);
        }

        [TestMethod]
        public void EnsureUniquePath_AppendsSuffixOnCollision()
        {
            var existing = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                @"C:\Temp\PN-01.SLDPRT",
                @"C:\Temp\PN-01_1.SLDPRT"
            };

            string path = PartNumberRenameHelper.EnsureUniquePath(
                @"C:\Temp",
                "PN-01",
                ".SLDPRT",
                candidate => existing.Contains(candidate));

            Assert.AreEqual(@"C:\Temp\PN-01_2.SLDPRT", path);
        }

        [TestMethod]
        public void EvaluateRenameDecision_BlocksUnsavedFiles()
        {
            RenameDecision decision = PartNumberRenameHelper.EvaluateRenameDecision(string.Empty, false, RenameMode.Safe);
            Assert.IsFalse(decision.Allowed);
            Assert.IsTrue(decision.Reason.Length > 0);
        }

        [TestMethod]
        public void EvaluateRenameDecision_BlocksReferencedWhenRequired()
        {
            RenameDecision decision = PartNumberRenameHelper.EvaluateRenameDecision("C:\\Temp\\A.SLDPRT", true, RenameMode.RenameIfNotReferenced);
            Assert.IsFalse(decision.Allowed);
        }

        [TestMethod]
        public void TryBuildUnsavedTargetPath_UsesSanitizedAllocatedName()
        {
            string message;
            string path;
            bool ok = PartNumberRenameHelper.TryBuildUnsavedTargetPath(
                @"C:\Temp",
                "PN:01",
                ".SLDPRT",
                _ => false,
                out path,
                out message);

            Assert.IsTrue(ok);
            Assert.AreEqual(string.Empty, message);
            Assert.AreEqual(@"C:\Temp\PN_01.SLDPRT", path);
        }

        [TestMethod]
        public void TryBuildUnsavedTargetPath_BlocksExistingTarget()
        {
            string message;
            string path;
            bool ok = PartNumberRenameHelper.TryBuildUnsavedTargetPath(
                @"C:\Temp",
                "PN-01",
                ".SLDPRT",
                candidate => string.Equals(candidate, @"C:\Temp\PN-01.SLDPRT", StringComparison.OrdinalIgnoreCase),
                out path,
                out message);

            Assert.IsFalse(ok);
            Assert.AreEqual(string.Empty, path);
            Assert.IsTrue(message.Contains("already exists"));
        }
    }
}
