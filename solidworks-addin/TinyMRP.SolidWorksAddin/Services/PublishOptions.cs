namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class PublishOptions
    {
        public string DeliverablesFolder { get; set; }
        public string BomFolder { get; set; }
        public bool ExportPngModel { get; set; }
        public bool ExportStep { get; set; }
        public bool ExportEdrawing { get; set; }
        public bool Export3mf { get; set; }
        public bool ExportPngDrawing { get; set; }
        public bool ExportPdf { get; set; }
        public bool ExportEdrawingDrawing { get; set; }
        public bool OverwriteFiles { get; set; }
        public bool TopLevelOnly { get; set; }
    }
}
