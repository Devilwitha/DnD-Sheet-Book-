using System;
using System.Collections.Generic;
using System.Windows.Media.Imaging;

namespace ElectroSchematic.Models
{
    public class Component
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string Name { get; set; }
        public string Type { get; set; }
        public double X { get; set; }
        public double Y { get; set; }
        public double Width { get; set; } = 50;
        public double Height { get; set; } = 50;
        public string ImagePath { get; set; }

        public List<Pin> Pins { get; set; } = new List<Pin>();

        public void UpdatePinPositions()
        {
            foreach (var pin in Pins)
            {
                pin.AbsoluteX = X + pin.OffsetX;
                pin.AbsoluteY = Y + pin.OffsetY;
            }
        }
    }
}
