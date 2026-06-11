using System;
using System.Collections.Generic;
using System.Windows;

namespace ElectroSchematic
{
    public static class OrthogonalRouter
    {
        public static List<Point> Route(Point start, Point end)
        {
            List<Point> points = new List<Point>();
            points.Add(start);

            // Simple L-shape routing or Z-shape routing.
            // Z-Shape routing horizontally:
            double midX = start.X + (end.X - start.X) / 2;

            points.Add(new Point(midX, start.Y));
            points.Add(new Point(midX, end.Y));
            points.Add(end);

            return points;
        }
    }
}
