using System;

namespace TinyMRP.SolidWorksAddin.Services
{
    [Flags]
    internal enum HideFeatureTypeFlags
    {
        None = 0,
        Origin = 1,
        RefPlane = 2,
        RefAxis = 4,
        RefPoint = 8,
        CoordSys = 16,
        Sketch2D = 32,
        Sketch3D = 64,
        Spline3D = 128,
        CompositeCurve = 256,
        Helix = 512
    }

    internal sealed class HideFeaturesOptions
    {
        public HideFeatureTypeFlags FeatureMask { get; set; } = HideFeatureTypeFlags.None;
        public bool AllConfigurations { get; set; }
        public bool HideEnvelopes { get; set; }
    }
}
