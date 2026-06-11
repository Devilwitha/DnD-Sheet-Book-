using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using ElectroSchematic.Models;
using System.Collections.Generic;

namespace ElectroSchematic
{
    public partial class MainWindow : Window
    {
        public bool IsSnappingEnabled { get; set; } = true;
        public double GridSize { get; set; } = 20.0;

        private Schematic _currentSchematic = new Schematic();
        private UIElement _draggedElement;
        private Point _dragStartPoint;
        private Models.Component _draggedComponent;

        // Wiring state
        private bool _isWiring = false;
        private Pin _startPin;
        private Polyline _previewWire;

        public MainWindow()
        {
            InitializeComponent();
            LoadLibrary();
            DrawGrid();
        }

        private void DrawGrid()
        {
            // Simple visual grid could be drawn here,
            // for now we set the background to a VisualBrush in XAML or dynamically.
            DrawingBrush gridBrush = new DrawingBrush
            {
                Viewport = new Rect(0, 0, GridSize, GridSize),
                ViewportUnits = BrushMappingMode.Absolute,
                TileMode = TileMode.Tile
            };

            GeometryDrawing drawing = new GeometryDrawing
            {
                Geometry = new RectangleGeometry(new Rect(0, 0, GridSize, GridSize)),
                Pen = new Pen(Brushes.LightGray, 0.5)
            };
            gridBrush.Drawing = drawing;
            DrawingCanvas.Background = gridBrush;
        }

        private void LoadLibrary()
        {
            ToolboxPanel.Children.Clear();
            ComponentLibrary.Load("library.json");
            foreach(var compDef in ComponentLibrary.AvailableComponents)
            {
                AddToolboxButton(compDef);
            }
        }

        private void AddToolboxButton(LibraryComponentDef def)
        {
            Button btn = new Button { Content = def.Name, Margin = new Thickness(5), Height = 30 };
            btn.PreviewMouseLeftButtonDown += (s, e) =>
            {
                // Start drag drop operation from toolbox
                DragDrop.DoDragDrop(btn, def.Name, DragDropEffects.Copy);
            };
            ToolboxPanel.Children.Add(btn);
        }

        private void New_Click(object sender, RoutedEventArgs e)
        {
            _currentSchematic = new Schematic();
            DrawingCanvas.Children.Clear();
        }
        private void Open_Click(object sender, RoutedEventArgs e)
        {
            Microsoft.Win32.OpenFileDialog dlg = new Microsoft.Win32.OpenFileDialog();
            dlg.DefaultExt = ".eschem";
            dlg.Filter = "ElectroSchematic Files (*.eschem)|*.eschem";
            if (dlg.ShowDialog() == true)
            {
                var json = System.IO.File.ReadAllText(dlg.FileName);
                _currentSchematic = Newtonsoft.Json.JsonConvert.DeserializeObject<Schematic>(json) ?? new Schematic();
                ReRenderCanvas();
            }
        }

        private void Save_Click(object sender, RoutedEventArgs e)
        {
            Microsoft.Win32.SaveFileDialog dlg = new Microsoft.Win32.SaveFileDialog();
            dlg.DefaultExt = ".eschem";
            dlg.Filter = "ElectroSchematic Files (*.eschem)|*.eschem";
            if (dlg.ShowDialog() == true)
            {
                var json = Newtonsoft.Json.JsonConvert.SerializeObject(_currentSchematic, Newtonsoft.Json.Formatting.Indented);
                System.IO.File.WriteAllText(dlg.FileName, json);
            }
        }

        private void ExportPdf_Click(object sender, RoutedEventArgs e)
        {
            Microsoft.Win32.SaveFileDialog dlg = new Microsoft.Win32.SaveFileDialog();
            dlg.DefaultExt = ".pdf";
            dlg.Filter = "PDF Documents (*.pdf)|*.pdf";
            if (dlg.ShowDialog() == true)
            {
                try
                {
                    // Create a new PDF document
                    PdfSharpCore.Pdf.PdfDocument document = new PdfSharpCore.Pdf.PdfDocument();
                    document.Info.Title = "ElectroSchematic Export";

                    // Create an empty page
                    PdfSharpCore.Pdf.PdfPage page = document.AddPage();
                    page.Size = PdfSharpCore.PageSize.A4;
                    page.Orientation = PdfSharpCore.PageOrientation.Landscape;

                    // Get an XGraphics object for drawing
                    PdfSharpCore.Drawing.XGraphics gfx = PdfSharpCore.Drawing.XGraphics.FromPdfPage(page);

                    // Font for text
                    PdfSharpCore.Drawing.XFont font = new PdfSharpCore.Drawing.XFont("Arial", 10, PdfSharpCore.Drawing.XFontStyle.Regular);

                    // Draw Components
                    foreach (var comp in _currentSchematic.Components)
                    {
                        // Draw box
                        PdfSharpCore.Drawing.XRect rect = new PdfSharpCore.Drawing.XRect(comp.X, comp.Y, comp.Width, comp.Height);
                        gfx.DrawRectangle(new PdfSharpCore.Drawing.XPen(PdfSharpCore.Drawing.XColors.DarkBlue, 2), PdfSharpCore.Drawing.XBrushes.LightBlue, rect);

                        // Draw text
                        gfx.DrawString(comp.Type, font, PdfSharpCore.Drawing.XBrushes.Black, rect, PdfSharpCore.Drawing.XStringFormats.Center);

                        // Draw pins
                        foreach(var pin in comp.Pins)
                        {
                            gfx.DrawEllipse(new PdfSharpCore.Drawing.XPen(PdfSharpCore.Drawing.XColors.Red, 1), PdfSharpCore.Drawing.XBrushes.Red,
                                comp.X + pin.OffsetX - 3, comp.Y + pin.OffsetY - 3, 6, 6);
                        }
                    }

                    // Draw Wires
                    foreach (var wire in _currentSchematic.Wires)
                    {
                        if (wire.Points != null && wire.Points.Count > 1)
                        {
                            var pen = new PdfSharpCore.Drawing.XPen(PdfSharpCore.Drawing.XColors.Black, 2);
                            for(int i = 0; i < wire.Points.Count - 1; i++)
                            {
                                gfx.DrawLine(pen, wire.Points[i].X, wire.Points[i].Y, wire.Points[i+1].X, wire.Points[i+1].Y);
                            }
                        }
                    }

                    // Save the document
                    document.Save(dlg.FileName);
                    MessageBox.Show("PDF exported successfully!", "Export PDF", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error exporting PDF: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }
        private void Exit_Click(object sender, RoutedEventArgs e) { Application.Current.Shutdown(); }

        private void SnapToggle_Click(object sender, RoutedEventArgs e)
        {
            IsSnappingEnabled = MenuSnapToggle.IsChecked;
        }

        private void AddCustomComponent_Click(object sender, RoutedEventArgs e)
        {
            Microsoft.Win32.OpenFileDialog dlg = new Microsoft.Win32.OpenFileDialog();
            dlg.Filter = "Image Files (*.png;*.jpg;*.jpeg)|*.png;*.jpg;*.jpeg";
            if (dlg.ShowDialog() == true)
            {
                var newDef = new LibraryComponentDef
                {
                    Name = System.IO.Path.GetFileNameWithoutExtension(dlg.FileName),
                    ImagePath = dlg.FileName,
                    Width = 60,
                    Height = 60,
                    Pins = new System.Collections.Generic.List<Models.Pin>
                    {
                        new Models.Pin { Name = "In", OffsetX = 0, OffsetY = 30 },
                        new Models.Pin { Name = "Out", OffsetX = 60, OffsetY = 30 }
                    }
                };

                ComponentLibrary.AvailableComponents.Add(newDef);
                ComponentLibrary.Save("library.json");
                LoadLibrary();
            }
        }

        // Drag and Drop from Toolbox to Canvas
        private void DrawingCanvas_Drop(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.StringFormat))
            {
                string componentType = (string)e.Data.GetData(DataFormats.StringFormat);
                Point dropPoint = e.GetPosition(DrawingCanvas);

                if (IsSnappingEnabled)
                {
                    dropPoint.X = Math.Round(dropPoint.X / GridSize) * GridSize;
                    dropPoint.Y = Math.Round(dropPoint.Y / GridSize) * GridSize;
                }

                var def = ComponentLibrary.AvailableComponents.FirstOrDefault(c => c.Name == componentType);
                if (def == null) return;

                var newComponent = new Models.Component
                {
                    Type = componentType,
                    Name = componentType + "_" + _currentSchematic.Components.Count,
                    X = dropPoint.X,
                    Y = dropPoint.Y,
                    Width = def.Width,
                    Height = def.Height,
                    ImagePath = def.ImagePath
                };

                // Copy pins from definition
                foreach(var pDef in def.Pins)
                {
                    newComponent.Pins.Add(new Pin { Name = pDef.Name, OffsetX = pDef.OffsetX, OffsetY = pDef.OffsetY });
                }
                newComponent.UpdatePinPositions();

                _currentSchematic.Components.Add(newComponent);
                RenderComponent(newComponent);
            }
        }

        private void RenderComponent(Models.Component comp)
        {
            Border border = new Border
            {
                Width = comp.Width,
                Height = comp.Height,
                BorderBrush = Brushes.DarkBlue,
                BorderThickness = new Thickness(2),
                Tag = comp // Store reference
            };

            if (!string.IsNullOrEmpty(comp.ImagePath) && System.IO.File.Exists(comp.ImagePath))
            {
                try
                {
                    System.Windows.Media.Imaging.BitmapImage bitmap = new System.Windows.Media.Imaging.BitmapImage(new Uri(comp.ImagePath));
                    Image img = new Image
                    {
                        Source = bitmap,
                        Stretch = Stretch.Uniform
                    };
                    border.Child = img;
                    border.Background = Brushes.Transparent;
                }
                catch
                {
                    // Fallback if image fails
                    SetTextFallback(border, comp);
                }
            }
            else
            {
                SetTextFallback(border, comp);
            }

            Canvas.SetLeft(border, comp.X);
            Canvas.SetTop(border, comp.Y);
            DrawingCanvas.Children.Add(border);

            // Render pins visually
            foreach(var pin in comp.Pins)
            {
                Ellipse el = new Ellipse
                {
                    Width = 6,
                    Height = 6,
                    Fill = Brushes.Red,
                    Tag = pin
                };
                Canvas.SetLeft(el, comp.X + pin.OffsetX - 3);
                Canvas.SetTop(el, comp.Y + pin.OffsetY - 3);
                DrawingCanvas.Children.Add(el);
            }
        }

        // Moving existing components on Canvas and Wiring
        private void Canvas_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.OriginalSource is FrameworkElement element)
            {
                if (element is Ellipse ellipse && ellipse.Tag is Pin pin)
                {
                    // Start wiring
                    _isWiring = true;
                    _startPin = pin;
                    _previewWire = new Polyline
                    {
                        Stroke = Brushes.Black,
                        StrokeThickness = 2
                    };
                    DrawingCanvas.Children.Add(_previewWire);
                    return;
                }

                Border border = element as Border ?? FindParent<Border>(element);
                if (border != null && border.Tag is Models.Component comp)
                {
                    _draggedElement = border;
                    _draggedComponent = comp;
                    _dragStartPoint = e.GetPosition(DrawingCanvas);
                    DrawingCanvas.CaptureMouse();
                }
            }
        }

        private void Canvas_MouseMove(object sender, MouseEventArgs e)
        {
            Point currentPoint = e.GetPosition(DrawingCanvas);

            if (_isWiring && _startPin != null && _previewWire != null)
            {
                var points = OrthogonalRouter.Route(new Point(_startPin.AbsoluteX, _startPin.AbsoluteY), currentPoint);
                _previewWire.Points.Clear();
                foreach(var p in points) _previewWire.Points.Add(p);
                return;
            }

            if (_draggedElement != null && _draggedComponent != null)
            {
                double newX = currentPoint.X - (_draggedComponent.Width / 2);
                double newY = currentPoint.Y - (_draggedComponent.Height / 2);

                if (IsSnappingEnabled)
                {
                    newX = Math.Round(newX / GridSize) * GridSize;
                    newY = Math.Round(newY / GridSize) * GridSize;
                }

                Canvas.SetLeft(_draggedElement, newX);
                Canvas.SetTop(_draggedElement, newY);
            }
        }

        private void Canvas_MouseLeftButtonUp(object sender, MouseButtonEventArgs e)
        {
            if (_isWiring)
            {
                if (e.OriginalSource is FrameworkElement element && element is Ellipse ellipse && ellipse.Tag is Pin endPin)
                {
                    if (_startPin != endPin)
                    {
                        var wire = new Wire
                        {
                            StartPinId = _startPin.Id,
                            EndPinId = endPin.Id,
                            Points = OrthogonalRouter.Route(new Point(_startPin.AbsoluteX, _startPin.AbsoluteY), new Point(endPin.AbsoluteX, endPin.AbsoluteY))
                        };
                        _currentSchematic.Wires.Add(wire);
                    }
                }

                _isWiring = false;
                _startPin = null;
                if (_previewWire != null)
                {
                    DrawingCanvas.Children.Remove(_previewWire);
                    _previewWire = null;
                }
                ReRenderCanvas();
                return;
            }

            if (_draggedElement != null && _draggedComponent != null)
            {
                _draggedComponent.X = Canvas.GetLeft(_draggedElement);
                _draggedComponent.Y = Canvas.GetTop(_draggedElement);
                _draggedComponent.UpdatePinPositions();

                DrawingCanvas.ReleaseMouseCapture();
                _draggedElement = null;
                _draggedComponent = null;

                // Re-render everything to update pin positions and wires
                ReRenderCanvas();
            }
        }

        private void ReRenderCanvas()
        {
            DrawingCanvas.Children.Clear();
            foreach (var comp in _currentSchematic.Components)
            {
                comp.UpdatePinPositions();
                RenderComponent(comp);
            }

            // Re-calculate and draw wires
            foreach (var wire in _currentSchematic.Wires)
            {
                var startPin = _currentSchematic.Components.SelectMany(c => c.Pins).FirstOrDefault(p => p.Id == wire.StartPinId);
                var endPin = _currentSchematic.Components.SelectMany(c => c.Pins).FirstOrDefault(p => p.Id == wire.EndPinId);

                if (startPin != null && endPin != null)
                {
                    wire.Points = OrthogonalRouter.Route(new Point(startPin.AbsoluteX, startPin.AbsoluteY), new Point(endPin.AbsoluteX, endPin.AbsoluteY));

                    Polyline pl = new Polyline
                    {
                        Stroke = Brushes.Black,
                        StrokeThickness = 2
                    };
                    foreach(var p in wire.Points) pl.Points.Add(p);
                    DrawingCanvas.Children.Add(pl);
                }
            }
        }

        private void SetTextFallback(Border border, Models.Component comp)
        {
            border.Background = Brushes.LightBlue;
            TextBlock tb = new TextBlock
            {
                Text = comp.Type,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                TextWrapping = TextWrapping.Wrap
            };
            border.Child = tb;
        }

        private T FindParent<T>(DependencyObject child) where T : DependencyObject
        {
            DependencyObject parentObject = VisualTreeHelper.GetParent(child);
            if (parentObject == null) return null;
            T parent = parentObject as T;
            if (parent != null) return parent;
            return FindParent<T>(parentObject);
        }
    }
}
