package com.gathin.tvhome;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.os.SystemClock;
import android.util.AttributeSet;
import android.view.View;

/**
 * Tiny procedural movement for the bundled gallery. A theme's catalogue position gives it a unique colour,
 * direction, speed, wave and mark. The view is not drawn while Home is hidden and honours Reduced motion.
 */
public final class ThemeMotionView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private int style;

    public ThemeMotionView(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    void configure(int themeIndex, boolean animations, boolean reducedMotion) {
        style = animations && !reducedMotion ? themeIndex : 0;
        setVisibility(style > 0 ? VISIBLE : GONE);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        if (style <= 0) return;
        float t = SystemClock.uptimeMillis() / 1000f, w = getWidth(), h = getHeight();
        float scale = Math.min(w, h) / 720f;
        paint.setColor(0x60FFFFFF);
        boolean vertical = (style & 1) != 0;
        for (int i = 0; i < 12; i++) {
            float seedX = (i * .618034f) % 1;
            float seedY = (i * .381966f + .17f) % 1;
            float progress = (seedX + t * (.006f + style % 6 * .004f)) % 1;
            float wave = (float) Math.sin(t * (.2f + style % 5 * .08f) + i * 2.4f)
                    * (.02f + style % 4 * .012f);
            float x = (vertical ? seedY + wave : progress) * w;
            float y = (vertical ? 1 - progress : seedY + wave) * h;
            canvas.drawCircle(x, y, (2.5f + i % 4 * 1.6f + style % 3) * scale, paint);
        }
        postInvalidateOnAnimation();
    }
}
