using System.Collections.Generic;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class NumberingModelsTests
    {
        [TestMethod]
        public void SequenceSegmentPayload_IncludesManualStartAndAutomaticFlag()
        {
            var segment = new NumberingSegmentDefinition
            {
                Kind = "seq",
                Padding = 4,
                Base = 10,
                StartAt = 9,
                AutoCounter = true
            };

            Dictionary<string, object> payload = segment.ToPayload();

            Assert.AreEqual("seq", payload["kind"]);
            Assert.AreEqual(4, payload["padding"]);
            Assert.AreEqual(10, payload["base"]);
            Assert.AreEqual(9, payload["start_at"]);
            Assert.AreEqual(true, payload["auto_counter"]);
        }

        [TestMethod]
        public void SequenceSegmentRoundTrip_ReadsManualStartAndAutomaticFlag()
        {
            var data = new Dictionary<string, object>
            {
                ["kind"] = "seq",
                ["padding"] = 5,
                ["base"] = 36,
                ["start_at"] = 12,
                ["auto_counter"] = true
            };

            NumberingSegmentDefinition segment = NumberingSegmentDefinition.FromDict(data);

            Assert.AreEqual("seq", segment.Kind);
            Assert.AreEqual(5, segment.Padding);
            Assert.AreEqual(36, segment.Base);
            Assert.AreEqual(12, segment.StartAt);
            Assert.IsTrue(segment.AutoCounter);
        }

        [TestMethod]
        public void SchemeRoundTrip_ReadsLastAllocatedPartNumber()
        {
            var data = new Dictionary<string, object>
            {
                ["id"] = "scheme-1",
                ["name"] = "Parts",
                ["last_part_number"] = "PART-0042"
            };

            NumberingSchemeDefinition scheme = NumberingSchemeDefinition.FromDictionary(data);

            Assert.AreEqual("PART-0042", scheme.LastPartNumber);
            Assert.IsTrue(scheme.LastPartNumberAvailable);
        }

        [TestMethod]
        public void SchemeRoundTrip_DetectsBackendWithoutLastAllocatedField()
        {
            var data = new Dictionary<string, object>
            {
                ["id"] = "scheme-1",
                ["name"] = "Parts"
            };

            NumberingSchemeDefinition scheme = NumberingSchemeDefinition.FromDictionary(data);

            Assert.IsFalse(scheme.LastPartNumberAvailable);
        }
    }
}
