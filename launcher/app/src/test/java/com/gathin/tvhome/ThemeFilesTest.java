package com.gathin.tvhome;

import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class ThemeFilesTest {
    @Test public void themeFilesAreAllowed() {
        assertEquals("config.json", ThemeFiles.path(Collections.singletonList("config.json")));
        assertEquals("wallpaper.jpg", ThemeFiles.path(Collections.singletonList("wallpaper.jpg")));
        assertEquals("theme_revision", ThemeFiles.path(Collections.singletonList("theme_revision")));
    }

    @Test public void collectionImagesAreAllowed() {
        assertEquals("wallpapers/dusk.jpg", ThemeFiles.path(Arrays.asList("wallpapers", "dusk.jpg")));
        assertEquals("wallpapers/Night_2.WEBP", ThemeFiles.path(Arrays.asList("wallpapers", "Night_2.WEBP")));
    }

    @Test public void theCollectionsCaptionsAreAllowed() {
        assertEquals("wallpapers/captions.txt", ThemeFiles.path(Arrays.asList("wallpapers", "captions.txt")));
        assertNull(ThemeFiles.path(Collections.singletonList("captions.txt")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", "notes.txt")));
        assertFalse(ThemeFiles.collectionImage("captions.txt"));
    }

    @Test public void anythingElseIsRefused() {
        assertNull(ThemeFiles.path(null));
        assertNull(ThemeFiles.path(Collections.emptyList()));
        assertNull(ThemeFiles.path(Collections.singletonList("cards.json")));
        assertNull(ThemeFiles.path(Collections.singletonList("..")));
        assertNull(ThemeFiles.path(Arrays.asList("..", "config.json")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", "..")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", "run.sh")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", "a b.jpg")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", "../config.jpg")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", ".jpg")));
        assertNull(ThemeFiles.path(Arrays.asList("other", "dusk.jpg")));
        assertNull(ThemeFiles.path(Arrays.asList("wallpapers", "sub", "dusk.jpg")));
    }

    @Test public void onlyTheBareFolderIsTheCollection() {
        assertTrue(ThemeFiles.isCollection(Collections.singletonList("wallpapers")));
        assertFalse(ThemeFiles.isCollection(Arrays.asList("wallpapers", "dusk.jpg")));
        assertFalse(ThemeFiles.isCollection(Collections.singletonList("config.json")));
    }

    @Test public void libraryCatalogAndThemeFilesAreAllowed() {
        assertEquals("catalog.json", ThemeFiles.libraryPath(Arrays.asList("library", "catalog.json")));
        assertEquals("ai-frontier/config.json",
                ThemeFiles.libraryPath(Arrays.asList("library", "ai-frontier", "config.json")));
        assertEquals("ai-frontier/wallpaper.jpg",
                ThemeFiles.libraryPath(Arrays.asList("library", "ai-frontier", "wallpaper.jpg")));
        assertEquals("ai-frontier/wallpapers/Night_2.WEBP",
                ThemeFiles.libraryPath(Arrays.asList("library", "ai-frontier", "wallpapers", "Night_2.WEBP")));
        assertEquals("ai-frontier/wallpapers/captions.txt",
                ThemeFiles.libraryPath(Arrays.asList("library", "ai-frontier", "wallpapers", "captions.txt")));
    }

    @Test public void unsafeOrUnknownLibraryPathsAreRefused() {
        assertNull(ThemeFiles.libraryPath(null));
        assertNull(ThemeFiles.libraryPath(Collections.emptyList()));
        assertNull(ThemeFiles.libraryPath(Collections.singletonList("library")));
        assertNull(ThemeFiles.libraryPath(Arrays.asList("library", "../personal", "config.json")));
        assertNull(ThemeFiles.libraryPath(Arrays.asList("library", "UPPER", "config.json")));
        assertNull(ThemeFiles.libraryPath(Arrays.asList("library", "ai-frontier", "notes.txt")));
        assertNull(ThemeFiles.libraryPath(Arrays.asList("library", "ai-frontier", "wallpapers", "../x.jpg")));
        assertNull(ThemeFiles.libraryPath(Arrays.asList("other", "catalog.json")));
    }
}
