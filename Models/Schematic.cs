using System;
using System.Collections.Generic;

namespace ElectroSchematic.Models
{
    public class Schematic
    {
        public List<Component> Components { get; set; } = new List<Component>();
        public List<Wire> Wires { get; set; } = new List<Wire>();
    }
}
