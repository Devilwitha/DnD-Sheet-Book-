using System;
using System.Collections.Generic;

namespace ElectroSchematic.Models
{
    public class Wire
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string StartPinId { get; set; }
        public string EndPinId { get; set; }
        public List<System.Windows.Point> Points { get; set; } = new List<System.Windows.Point>();
    }
}
