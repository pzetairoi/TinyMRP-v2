using System.Collections.Generic;

namespace TinyMRP.SolidWorksAddin.Models
{
    public class DocPackOptions
    {
        public IList<string> FileTypes { get; set; } = new List<string>();
        public IList<string> Processes { get; set; } = new List<string>();
    }

    public class DocPackRequest
    {
        public string PartNumber { get; set; } = string.Empty;
        public string? Revision { get; set; }
        public string Depth { get; set; } = "full";
        public bool IncludeConsumed { get; set; }
        public string Classified { get; set; } = "show";
        public string ProcessMode { get; set; } = "all";
        public IList<string> Processes { get; set; } = new List<string>();
        public IList<string> FileTypes { get; set; } = new List<string>();
        public bool ExcelBom { get; set; }
        public bool PdfBinder { get; set; }
        public bool VisualList { get; set; }
        public bool SelectedFiles { get; set; }
        public bool FabricationPack { get; set; }
        public bool BinderAddIndex { get; set; }
        public bool BinderAddDatasheets { get; set; }
        public bool BinderPageNumbers { get; set; }
        public bool StampQuote { get; set; }
        public bool StampConfidential { get; set; }
        public bool StampApproved { get; set; }
        public bool StampWip { get; set; }
        public bool StampInProgress { get; set; }
    }

    public class DocPackBuildResult
    {
        public string LocalPath { get; set; } = string.Empty;
        public string? HttpUrl { get; set; }
        public string? FileName { get; set; }
    }
}
