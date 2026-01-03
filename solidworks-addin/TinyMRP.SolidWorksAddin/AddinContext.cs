using System;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using SolidWorks.Interop.sldworks;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin
{
    internal static class AddinContext
    {
        public static ISldWorks SldWorks { get; private set; }
        public static TinyMrpConfig Config { get; private set; }
        public static TinyMrpPublisher Publisher { get; private set; }

        public static void Initialize(ISldWorks swApp)
        {
            SldWorks = swApp;
            try
            {
                string addinDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                Config = TinyMrpConfig.Load(addinDir);
                Publisher = new TinyMrpPublisher(swApp, Config);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to initialize TinyMRP add-in: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        public static void Clear()
        {
            Publisher = null;
            Config = null;
            SldWorks = null;
        }
    }
}
