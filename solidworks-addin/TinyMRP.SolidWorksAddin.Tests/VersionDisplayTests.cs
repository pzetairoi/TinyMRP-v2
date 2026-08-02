using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class VersionDisplayTests
    {
        [TestMethod]
        public void FormatTitle_UsesOnlyIntegerBuildNumber()
        {
            Assert.AreEqual("TinyMRP V339", SwAddin.FormatTitle("TinyMRP", "339", "1.0.0.339"));
        }

        [TestMethod]
        public void FormatTitle_CleansLegacyInformationalVersion()
        {
            Assert.AreEqual(
                "TinyMRP V337",
                SwAddin.FormatTitle("TinyMRP", "1.0.0+build.337.1bab0a04.20260802120000", "1.0.0.337"));
        }

        [TestMethod]
        public void FormatTitle_FallsBackToFileVersionRevision()
        {
            Assert.AreEqual("TinyMRP V340", SwAddin.FormatTitle("TinyMRP", string.Empty, "1.0.0.340"));
        }
    }
}
