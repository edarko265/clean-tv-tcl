package com.gathin.tvhome;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** Offline theme packs installed beside the APK and selected with the TV remote. */
final class ThemeLibrary {
    private static final String DIR = "theme-library";
    private static final String PREFS = "theme_library_state";
    private static final String CURRENT = "current_theme";
    private static final String PERSONAL = "personal";
    private static final Pattern SAFE_ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,47}");

    static final class Theme {
        final String id;
        final String name;

        Theme(String id, String name) {
            this.id = id;
            this.name = name;
        }
    }

    private ThemeLibrary() {}

    static File dir(Context context) {
        return new File(context.getFilesDir(), DIR);
    }

    /** Config uses this so a preference selects a pack without copying private pictures. */
    static File activeDir(Context context, File personal) {
        String id = currentId(context);
        File selected = new File(dir(context), id);
        return !PERSONAL.equals(id) && hasTheme(selected) ? selected : personal;
    }

    static void markExternal(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(CURRENT, PERSONAL).apply();
    }

    static String currentId(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(CURRENT, PERSONAL);
    }

    /** One-based catalogue position for ThemeMotionView; Personal and a missing pack stay still. */
    static int currentMotion(Context context) {
        String current = currentId(context);
        int position = 0;
        for (Theme theme : themes(context)) {
            if (PERSONAL.equals(theme.id)) continue;
            position++;
            if (current.equals(theme.id)) return position;
        }
        return 0;
    }

    static List<Theme> themes(Context context) {
        List<Theme> out = new ArrayList<>();
        File personal = Config.externalDir(context);
        if (hasTheme(personal)) out.add(new Theme(PERSONAL, personalName(personal)));
        try {
            JSONObject root = new JSONObject(readText(new File(dir(context), "catalog.json")));
            JSONArray list = root.optJSONArray("themes");
            if (list == null) return out;
            for (int i = 0; i < list.length(); i++) {
                JSONObject item = list.optJSONObject(i);
                if (item == null) continue;
                String id = item.optString("id", "").trim();
                String name = item.optString("name", "").trim();
                if (SAFE_ID.matcher(id).matches() && !name.isEmpty() && !contains(out, id)
                        && hasTheme(new File(dir(context), id))) out.add(new Theme(id, name));
            }
        } catch (Exception ignored) {}
        return out;
    }

    static String currentName(Context context) {
        String current = currentId(context);
        for (Theme theme : themes(context)) if (theme.id.equals(current)) return theme.name;
        return "Personal / external";
    }

    static boolean apply(Context context, String id) {
        if (!contains(themes(context), id)) return false;
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(CURRENT, id).commit();
    }

    private static String personalName(File folder) {
        try {
            String name = new JSONObject(readText(new File(folder, Config.FILE_NAME)))
                    .optString("greeting_name", "").trim();
            if (!name.isEmpty()) return name;
        } catch (Exception ignored) {}
        return "Personal / external";
    }

    private static boolean contains(List<Theme> themes, String id) {
        for (Theme theme : themes) if (theme.id.equals(id)) return true;
        return false;
    }

    private static boolean hasTheme(File folder) {
        return folder != null && new File(folder, Config.FILE_NAME).isFile();
    }

    private static String readText(File file) throws Exception {
        if (!file.isFile() || file.length() <= 0 || file.length() > 64 * 1024)
            throw new Exception("missing or oversized file");
        byte[] bytes = new byte[(int) file.length()];
        try (FileInputStream input = new FileInputStream(file)) {
            int count = input.read(bytes);
            return new String(bytes, 0, count, StandardCharsets.UTF_8);
        }
    }
}
