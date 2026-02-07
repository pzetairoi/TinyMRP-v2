using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class ComInteropUtil
    {
        // SolidWorks COM APIs often return SAFEARRAY values that marshal as System.Array (not object[]).
        // This helper provides SAFEARRAY-safe enumeration without relying on brittle casts.
        public static IEnumerable<object> EnumerateCom(object comValue)
        {
            if (comValue == null)
            {
                yield break;
            }

            Array array = comValue as Array;
            if (array != null)
            {
                foreach (object item in array)
                {
                    yield return item;
                }

                yield break;
            }

            yield return comValue;
        }

        public static IEnumerable<T> EnumerateComAs<T>(object comValue)
        {
            foreach (object obj in EnumerateCom(comValue))
            {
                if (obj is T)
                {
                    yield return (T)obj;
                }
            }
        }

        public static int GetComLength(object comValue)
        {
            if (comValue == null)
            {
                return 0;
            }

            Array array = comValue as Array;
            if (array != null)
            {
                return array.Length;
            }

            return 1;
        }

        public static void TryFinalReleaseComObject(object comObject)
        {
            if (comObject == null)
            {
                return;
            }

            try
            {
                if (Marshal.IsComObject(comObject))
                {
                    Marshal.FinalReleaseComObject(comObject);
                }
            }
            catch
            {
                // ignore release errors
            }
        }
    }
}
