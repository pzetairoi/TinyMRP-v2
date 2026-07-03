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

        private static object InvokePrivate(object target, string methodName, params object[] args)
        {
            MethodInfo method = target.GetType().GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Instance);
            Assert.IsNotNull(method);
            return method.Invoke(target, args);
        }

        private static Type GetPlannedRefType()
        {
            Type plannedRefType = typeof(TinyMrpPublisher).GetNestedType("PlannedRef", BindingFlags.NonPublic);
            Assert.IsNotNull(plannedRefType);
            return plannedRefType;
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
