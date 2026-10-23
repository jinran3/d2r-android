// TotK Android 移植 —— 新工程 R0 骨架的入口。
// 这一层只做三件事：起一个全屏 Activity、画一块纯色（证明 Surface 通了）、把启动事实写进 files/app.log。
// 不加载游戏、不碰 NVN、不读数据包 —— 那些是 R1 之后的事。
// TotK Android port -- entry point of the new project's R0 skeleton.
// This layer does exactly three things: start a full-screen Activity, paint a solid colour (proving the surface works)
// and write the boot facts into files/app.log. It does not load the game, touch NVN or read the data package.
package org.totk.android.port;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

public final class MainActivity extends Activity {
    static final String TAG = "TotkApp";
    static final String VERSION = "R0-1.0";

    private static File sLogFile;
    private static final Object sLogLock = new Object();

    /** 同时写 logcat 与私有目录 files/app.log；R0 的判据只看 app.log 的前两行。 */
    static void log(String line) {
        android.util.Log.i(TAG, line);
        synchronized (sLogLock) {
            if (sLogFile == null) return;
            try (FileWriter w = new FileWriter(sLogFile, true)) {
                w.write(line);
                w.write('\n');
            } catch (IOException ignored) {
                // 日志写不进去不能拖垮启动；logcat 那条还在
            }
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        sLogFile = new File(getFilesDir(), "app.log");
        log("totk-app " + VERSION + " package=" + getPackageName()
                + " abi=" + Build.SUPPORTED_ABIS[0]
                + " sdk=" + Build.VERSION.SDK_INT
                + " device=" + Build.MODEL);
        setContentView(new StageView(this));
    }

    @Override
    protected void onResume() {
        super.onResume();
        log("resumed");
    }

    /** R0 的舞台：一块纯色 + 一行版本字。尺寸变化时把 Surface 实际像素写进日志。 */
    static final class StageView extends View {
        private final Paint mPaint = new Paint();
        private final Paint mText = new Paint(Paint.ANTI_ALIAS_FLAG);
        private int mW, mH;

        StageView(Activity host) {
            super(host);
            mPaint.setColor(Color.rgb(0x0B, 0x1B, 0x2A));   // 深蓝，便于和黑屏区分
            mText.setColor(Color.WHITE);
            mText.setTextSize(48f);
        }

        @Override
        protected void onSizeChanged(int w, int h, int oldw, int oldh) {
            super.onSizeChanged(w, h, oldw, oldh);
            mW = w;
            mH = h;
            log("surface " + w + "x" + h);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            canvas.drawRect(0, 0, mW, mH, mPaint);
            canvas.drawText("totk-app " + VERSION + "  " + mW + "x" + mH, 64f, 120f, mText);
        }
    }
}
