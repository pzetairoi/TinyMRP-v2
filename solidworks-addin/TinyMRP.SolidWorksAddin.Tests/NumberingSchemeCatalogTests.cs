using System.Linq;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class NumberingSchemeCatalogTests
    {
        [TestMethod]
        public void GetSelectableSchemes_UsesActiveSchemesInsteadOfLegacyPresetFlags()
        {
            var schemes = new[]
            {
                new NumberingSchemeDefinition
                {
                    Id = "simple",
                    Name = "Simple",
                    IsActive = true,
                    IsPreset = false,
                    Visibility = "advanced_only"
                },
                new NumberingSchemeDefinition
                {
                    Id = "inactive-preset",
                    Name = "Inactive preset",
                    IsActive = false,
                    IsPreset = true,
                    Visibility = "quickstart"
                },
                new NumberingSchemeDefinition
                {
                    Id = "recommended",
                    Name = "Recommended",
                    IsActive = true,
                    IsRecommended = true,
                    IsPreset = false,
                    Visibility = "advanced_only"
                }
            };

            var selectable = NumberingSchemeCatalog.GetSelectableSchemes(schemes);

            CollectionAssert.AreEqual(
                new[] { "simple", "recommended" },
                selectable.Select(scheme => scheme.Id).ToArray());
        }

        [TestMethod]
        public void CreateBasicScheme_SeedsSimpleCurrentDefaults()
        {
            NumberingSchemeDefinition scheme = NumberingSchemeCatalog.CreateBasicScheme();

            Assert.IsTrue(scheme.IsActive);
            Assert.AreEqual("-", scheme.Separator);
            Assert.AreEqual("global", scheme.ScopeMode);
            Assert.AreEqual(6, scheme.Seq.Padding);
            Assert.AreEqual(10, scheme.Seq.Base);
            Assert.AreEqual(1, scheme.Seq.StartAt);
            Assert.AreEqual("never", scheme.Seq.ResetPolicy);
            // New parts stay revision-less by default; "A" is only used when alpha is chosen explicitly.
            Assert.AreEqual("none", scheme.Revision.Policy);
            Assert.AreEqual(string.Empty, scheme.Revision.Start);
            Assert.AreEqual(32, scheme.ValidationRules.MaxLength);
            Assert.AreEqual("A-Z0-9-", scheme.ValidationRules.AllowedCharset);
            Assert.IsTrue(scheme.ValidationRules.RequireSeqSegment);
            Assert.AreEqual(2, scheme.PatternSegments.Count);
            Assert.AreEqual("literal", scheme.PatternSegments[0].Kind);
            Assert.AreEqual("PART", scheme.PatternSegments[0].Value);
            Assert.AreEqual("seq", scheme.PatternSegments[1].Kind);
            Assert.AreEqual(6, scheme.PatternSegments[1].Padding);
            Assert.AreEqual(10, scheme.PatternSegments[1].Base);
            Assert.AreEqual(1, scheme.PatternSegments[1].StartAt);
            Assert.IsTrue(scheme.PatternSegments[1].AutoCounter);
        }

        [TestMethod]
        public void ApplyBasicTemplate_CanBuildSequenceOnlyScheme()
        {
            var scheme = new NumberingSchemeDefinition
            {
                Name = "Sequence only"
            };

            NumberingSchemeCatalog.ApplyBasicTemplate(scheme, string.Empty, 6, false);

            Assert.AreEqual(1, scheme.PatternSegments.Count);
            Assert.AreEqual("seq", scheme.PatternSegments[0].Kind);
            Assert.AreEqual(1, scheme.Seq.StartAt);
            Assert.IsTrue(scheme.PatternSegments[0].AutoCounter);
        }
    }
}
