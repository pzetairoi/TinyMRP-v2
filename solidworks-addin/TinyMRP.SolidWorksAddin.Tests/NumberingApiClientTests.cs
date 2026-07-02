using System.Linq;
using System.Net.Http;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.Tests
{
    [TestClass]
    public class NumberingApiClientTests
    {
        [TestMethod]
        public void NormalizeBaseUrl_DefaultsToHttpsForPublicHost()
        {
            Assert.AreEqual("https://example.com", NumberingApiClient.NormalizeBaseUrl("example.com"));
        }

        [TestMethod]
        public void NormalizeBaseUrl_StripsTrailingApiPath()
        {
            Assert.AreEqual("https://example.com", NumberingApiClient.NormalizeBaseUrl("https://example.com/api"));
        }

        [TestMethod]
        public void NormalizeBaseUrl_StripsTrailingApiNumberingPath()
        {
            Assert.AreEqual("https://example.com", NumberingApiClient.NormalizeBaseUrl("https://example.com/api/numbering"));
        }

        [TestMethod]
        public void NormalizeBaseUrl_DefaultsToHttpForLocalhost()
        {
            Assert.AreEqual("http://localhost:8000", NumberingApiClient.NormalizeBaseUrl("localhost:8000"));
        }

        [TestMethod]
        public void NormalizeBaseUrl_PreservesExplicitHttpForLocalhost()
        {
            Assert.AreEqual("http://localhost:8000", NumberingApiClient.NormalizeBaseUrl("http://localhost:8000/api"));
        }

        [TestMethod]
        public void AddAuthHeaders_SendsAllSupportedTokenHeaders()
        {
            using (var request = new HttpRequestMessage(HttpMethod.Get, "https://example.com/api/auth/check"))
            {
                NumberingApiClient.AddAuthHeaders(request, "tmrp_raw_token");

                Assert.AreEqual("Bearer tmrp_raw_token", request.Headers.GetValues("Authorization").Single());
                Assert.AreEqual("tmrp_raw_token", request.Headers.GetValues("Authentication-Token").Single());
                Assert.AreEqual("tmrp_raw_token", request.Headers.GetValues("X-Auth-Token").Single());
            }
        }
    }
}
