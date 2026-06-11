using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;

namespace ElectroSchematic
{
    public class LibraryComponentDef
    {
        public string Name { get; set; }
        public double Width { get; set; } = 50;
        public double Height { get; set; } = 50;
        public string ImagePath { get; set; }
        public List<Models.Pin> Pins { get; set; } = new List<Models.Pin>();
    }

    public static class ComponentLibrary
    {
        public static List<LibraryComponentDef> AvailableComponents = new List<LibraryComponentDef>();

        public static void Load(string libraryPath)
        {
            if (File.Exists(libraryPath))
            {
                var json = File.ReadAllText(libraryPath);
                AvailableComponents = JsonConvert.DeserializeObject<List<LibraryComponentDef>>(json) ?? new List<LibraryComponentDef>();
            }
            else
            {
                // Defaults
                AvailableComponents.Add(new LibraryComponentDef
                {
                    Name = "Resistor",
                    Pins = new List<Models.Pin> {
                        new Models.Pin { Name = "In", OffsetX = 0, OffsetY = 25 },
                        new Models.Pin { Name = "Out", OffsetX = 50, OffsetY = 25 }
                    }
                });
                AvailableComponents.Add(new LibraryComponentDef
                {
                    Name = "Capacitor",
                    Pins = new List<Models.Pin> {
                        new Models.Pin { Name = "In", OffsetX = 0, OffsetY = 25 },
                        new Models.Pin { Name = "Out", OffsetX = 50, OffsetY = 25 }
                    }
                });
                AvailableComponents.Add(new LibraryComponentDef
                {
                    Name = "Siemens S7-1200",
                    Width = 100, Height = 100,
                    Pins = new List<Models.Pin> {
                        new Models.Pin { Name = "L+", OffsetX = 10, OffsetY = 0 },
                        new Models.Pin { Name = "M", OffsetX = 30, OffsetY = 0 },
                        new Models.Pin { Name = "Q0.0", OffsetX = 10, OffsetY = 100 },
                        new Models.Pin { Name = "Q0.1", OffsetX = 30, OffsetY = 100 }
                    }
                });
            }
        }

        public static void Save(string libraryPath)
        {
            var json = JsonConvert.SerializeObject(AvailableComponents, Formatting.Indented);
            File.WriteAllText(libraryPath, json);
        }
    }
}
