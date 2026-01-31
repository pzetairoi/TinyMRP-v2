using System;
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

        private static object InvokePrivate(object target, string methodName, params object[] args)
        {
            MethodInfo method = target.GetType().GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Instance);
            Assert.IsNotNull(method);
            return method.Invoke(target, args);
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
    }
}
