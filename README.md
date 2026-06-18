# ElectroSchematic Editor

A C# WPF application for drawing, saving, and exporting electronic and electrical schematics.

## Features

- **Component Library**: Includes basic components (Resistors, Capacitors) and specific devices (like the Siemens S7-1200).
- **Custom Components**: Add your own custom components by importing an image (PNG, JPG) and defining connection pins.
- **Drag & Drop**: Easily drag components from the toolbox onto the drawing canvas.
- **Snapping**: Toggleable grid snapping ensures your schematics stay aligned and neat.
- **Orthogonal Wiring**: Draw clean, right-angled connections between component pins.
- **Save & Load**: Save your projects natively as `.eschem` (JSON) files and reload them later.
- **PDF Export**: Export your completed schematics directly to A4 Landscape PDF format.

## Getting Started

### Prerequisites

- [.NET SDK](https://dotnet.microsoft.com/download) (Version 10.0 or higher recommended)

### Building and Running

To build the project, run:
```bash
dotnet build
```

To run the application, use:
```bash
dotnet run --project ElectroSchematic
```

## Usage

1. **Adding Components**: Drag a component from the left-hand Toolbox onto the canvas.
2. **Wiring**: Click on a red pin on a component, move your mouse, and click on a target pin on another component to create a wire.
3. **Custom Components**: Go to `Library > Add Custom Component...` to import an image and create a new reusable part for your schematics.
4. **Exporting**: Go to `File > Export PDF` to save your work as a PDF.

## Notes

- For Linux/Mac development environments, building WPF requires setting `<EnableWindowsTargeting>true</EnableWindowsTargeting>` (already included in `Directory.Build.props`).
