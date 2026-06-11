using System;

namespace ElectroSchematic.Models
{
    public class Pin
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string Name { get; set; }
        public double OffsetX { get; set; }
        public double OffsetY { get; set; }

        // Relative to Component position
        public double AbsoluteX { get; set; }
        public double AbsoluteY { get; set; }
    }
}
