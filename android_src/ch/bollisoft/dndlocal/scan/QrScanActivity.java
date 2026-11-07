package ch.bollisoft.dndlocal.scan;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.ImageFormat;
import android.hardware.Camera;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.google.zxing.BinaryBitmap;
import com.google.zxing.PlanarYUVLuminanceSource;
import com.google.zxing.Result;
import com.google.zxing.common.HybridBinarizer;
import com.google.zxing.qrcode.QRCodeReader;
import java.util.List;

/** A bundled offline QR-only scanner. Camera lifetime is bounded by this visible activity. */
@SuppressWarnings("deprecation")
public final class QrScanActivity extends Activity implements SurfaceHolder.Callback, Camera.PreviewCallback {
    private Camera camera;
    private SurfaceView preview;
    private TextView status;
    private boolean resumed, surfaceReady, done;
    private long lastFrame;
    private int width, height;
    private final QRCodeReader reader = new QRCodeReader();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(16, 24, 16, 24);
        layout.setBackgroundColor(Color.rgb(20, 24, 30));
        status = new TextView(this);
        status.setText("QR-Code der Spielleitung in die Kamera halten.\nEs werden keine Bilder gespeichert oder übertragen.");
        status.setTextColor(Color.WHITE);
        status.setTextSize(18);
        status.setGravity(Gravity.CENTER);
        layout.addView(status, new LinearLayout.LayoutParams(-1, -2));
        preview = new SurfaceView(this);
        preview.getHolder().addCallback(this);
        layout.addView(preview, new LinearLayout.LayoutParams(-1, 0, 1));
        Button close = new Button(this);
        close.setText("Scan abbrechen");
        close.setOnClickListener(v -> finish());
        layout.addView(close, new LinearLayout.LayoutParams(-1, -2));
        setContentView(layout);
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, 17);
        }
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(request, permissions, grants);
        if (request != 17) return;
        if (grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED) startCamera();
        else fail("Kamerazugriff wurde nicht erlaubt. Adresse und Code können weiterhin manuell eingegeben werden.");
    }

    @Override protected void onResume() { super.onResume(); resumed = true; startCamera(); }
    @Override protected void onPause() { resumed = false; stopCamera(); super.onPause(); }
    @Override protected void onDestroy() { stopCamera(); super.onDestroy(); }
    @Override public void surfaceCreated(SurfaceHolder holder) { surfaceReady = true; startCamera(); }
    @Override public void surfaceChanged(SurfaceHolder holder, int format, int w, int h) { }
    @Override public void surfaceDestroyed(SurfaceHolder holder) { surfaceReady = false; stopCamera(); }

    private void startCamera() {
        if (!resumed || !surfaceReady || done || camera != null) return;
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return;
        try {
            int id = -1;
            Camera.CameraInfo info = new Camera.CameraInfo();
            for (int i = 0; i < Camera.getNumberOfCameras(); i++) {
                Camera.getCameraInfo(i, info);
                if (info.facing == Camera.CameraInfo.CAMERA_FACING_BACK) { id = i; break; }
            }
            if (id < 0) throw new IllegalStateException("no rear camera");
            Camera.getCameraInfo(id, info);
            camera = Camera.open(id);
            Camera.Parameters p = camera.getParameters();
            Camera.Size chosen = p.getPreviewSize();
            List<Camera.Size> sizes = p.getSupportedPreviewSizes();
            int best = Integer.MAX_VALUE;
            for (Camera.Size s : sizes) {
                if (s.width <= 1280 && s.height <= 960) {
                    int score = Math.abs(s.width * s.height - 640 * 480);
                    if (score < best) { chosen = s; best = score; }
                }
            }
            p.setPreviewSize(chosen.width, chosen.height);
            p.setPreviewFormat(ImageFormat.NV21);
            List<String> modes = p.getSupportedFocusModes();
            if (modes != null && modes.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE))
                p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
            camera.setParameters(p);
            width = chosen.width;
            height = chosen.height;
            int rotation = getWindowManager().getDefaultDisplay().getRotation();
            int degrees = rotation == Surface.ROTATION_90 ? 90 : rotation == Surface.ROTATION_180 ? 180 : rotation == Surface.ROTATION_270 ? 270 : 0;
            camera.setDisplayOrientation((info.orientation - degrees + 360) % 360);
            camera.setPreviewDisplay(preview.getHolder());
            camera.setPreviewCallback(this);
            camera.startPreview();
        } catch (Exception error) {
            stopCamera();
            fail("Die Kamera ist nicht verfügbar. Bitte andere Kamera-Apps schließen oder den Code manuell eingeben.");
        }
    }

    private void stopCamera() {
        Camera old = camera;
        camera = null;
        if (old != null) {
            try { old.setPreviewCallback(null); old.stopPreview(); } catch (Exception ignored) { }
            old.release();
        }
    }

    @Override public void onPreviewFrame(byte[] data, Camera source) {
        long now = SystemClock.elapsedRealtime();
        if (done || !resumed || now - lastFrame < 350 || data == null) return;
        lastFrame = now;
        try {
            PlanarYUVLuminanceSource luminance = new PlanarYUVLuminanceSource(data, width, height, 0, 0, width, height, false);
            Result result = reader.decode(new BinaryBitmap(new HybridBinarizer(luminance)));
            String text = result.getText();
            if (text == null || text.length() > 1024 || !text.contains("\"dnd-local\"")) {
                status.setText("Kein DnD-Lokal-Beitrittscode. Bitte den QR-Code der Spielleitung scannen.");
                return;
            }
            done = true;
            stopCamera();
            setResult(RESULT_OK, new Intent().putExtra("dnd_qr", text));
            finish();
        } catch (com.google.zxing.ReaderException ignored) {
            // No QR in this frame; retry while this activity is visible.
        } finally { reader.reset(); }
    }

    private void fail(String message) {
        done = true;
        setResult(RESULT_CANCELED, new Intent().putExtra("dnd_error", message));
        finish();
    }
}
