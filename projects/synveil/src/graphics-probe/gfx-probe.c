// SPDX-License-Identifier: MPL-2.0
// Graphics payload probe (ADR 0027): dlopen-based, header-free
// check that the sealed Mesa + Vulkan payload initializes in
// the guest. Vulkan: create an instance through the staged
// loader and enumerate physical devices — the lavapipe
// software device (llvmpipe) must appear. GL: initialize EGL
// on Mesa's surfaceless platform, make a context current with
// no surface, and read the GL strings — the renderer must be
// llvmpipe. Every fact is printed as a GFX_* line; the probe
// exits 0 (and prints GFX_PROBE_OK) only when both halves
// initialize with the software drivers. It proves the layer
// initializes under QEMU/TCG software rendering — never
// real-GPU behaviour or performance.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* ---- Vulkan (minimal ABI declarations; no vendor headers) ---- */

typedef int32_t gfx_vk_result;
typedef void *gfx_vk_instance;
typedef void *gfx_vk_physical_device;

struct gfx_vk_app_info {
    uint32_t s_type;
    const void *next;
    const char *application_name;
    uint32_t application_version;
    const char *engine_name;
    uint32_t engine_version;
    uint32_t api_version;
};

struct gfx_vk_instance_info {
    uint32_t s_type;
    const void *next;
    uint32_t flags;
    const struct gfx_vk_app_info *application_info;
    uint32_t layer_count;
    const char *const *layers;
    uint32_t extension_count;
    const char *const *extensions;
};

/* VkPhysicalDeviceProperties: only the leading fields are
 * read (apiVersion .. deviceName); the tail is slack for the
 * limits/sparse blocks the driver writes in full. */
struct gfx_vk_props {
    uint32_t api_version;
    uint32_t driver_version;
    uint32_t vendor_id;
    uint32_t device_id;
    uint32_t device_type;
    char device_name[256];
    uint8_t rest[1024];
};

typedef gfx_vk_result (*gfx_vk_create_instance_fn)(
    const struct gfx_vk_instance_info *, const void *,
    gfx_vk_instance *);
typedef gfx_vk_result (*gfx_vk_enumerate_devices_fn)(
    gfx_vk_instance, uint32_t *, gfx_vk_physical_device *);
typedef void (*gfx_vk_device_props_fn)(gfx_vk_physical_device,
                                       struct gfx_vk_props *);
typedef void (*gfx_vk_destroy_instance_fn)(gfx_vk_instance,
                                           const void *);

static int probe_vulkan(void)
{
    void *lib = dlopen("libvulkan.so.1", RTLD_NOW);
    if (!lib) {
        printf("GFX_VULKAN_FAIL dlopen: %s\n", dlerror());
        return 0;
    }
    gfx_vk_create_instance_fn create = (gfx_vk_create_instance_fn)
        dlsym(lib, "vkCreateInstance");
    gfx_vk_enumerate_devices_fn enumerate =
        (gfx_vk_enumerate_devices_fn)
        dlsym(lib, "vkEnumeratePhysicalDevices");
    gfx_vk_device_props_fn props = (gfx_vk_device_props_fn)
        dlsym(lib, "vkGetPhysicalDeviceProperties");
    gfx_vk_destroy_instance_fn destroy = (gfx_vk_destroy_instance_fn)
        dlsym(lib, "vkDestroyInstance");
    if (!create || !enumerate || !props || !destroy) {
        printf("GFX_VULKAN_FAIL loader entry points missing\n");
        return 0;
    }
    struct gfx_vk_app_info app = {0, NULL, "synveil-gfx-probe", 1,
                                  NULL, 0, (1u << 22)};
    struct gfx_vk_instance_info info = {1, NULL, 0, &app, 0, NULL,
                                        0, NULL};
    gfx_vk_instance instance = NULL;
    gfx_vk_result result = create(&info, NULL, &instance);
    if (result != 0 || !instance) {
        printf("GFX_VULKAN_FAIL vkCreateInstance=%d\n", result);
        return 0;
    }
    uint32_t count = 0;
    result = enumerate(instance, &count, NULL);
    if (result != 0 || count == 0 || count > 16) {
        printf("GFX_VULKAN_FAIL enumerate=%d count=%u\n", result,
               count);
        destroy(instance, NULL);
        return 0;
    }
    gfx_vk_physical_device devices[16];
    result = enumerate(instance, &count, devices);
    if (result != 0) {
        printf("GFX_VULKAN_FAIL enumerate2=%d\n", result);
        destroy(instance, NULL);
        return 0;
    }
    int software = 0;
    for (uint32_t i = 0; i < count; i++) {
        struct gfx_vk_props device_props;
        memset(&device_props, 0, sizeof(device_props));
        props(devices[i], &device_props);
        printf("GFX_VULKAN_DEVICE name=\"%s\" type=%u api=%u.%u.%u\n",
               device_props.device_name, device_props.device_type,
               device_props.api_version >> 22,
               (device_props.api_version >> 12) & 0x3ff,
               device_props.api_version & 0xfff);
        if (strstr(device_props.device_name, "llvmpipe"))
            software = 1;
    }
    destroy(instance, NULL);
    if (!software) {
        printf("GFX_VULKAN_FAIL no llvmpipe (lavapipe) device\n");
        return 0;
    }
    printf("GFX_VULKAN_OK devices=%u driver=lavapipe\n", count);
    return 1;
}

/* ---- EGL / OpenGL (minimal ABI declarations) ---- */

typedef void *gfx_egl_display;
typedef void *gfx_egl_config;
typedef void *gfx_egl_context;
typedef unsigned int gfx_egl_bool;
typedef int32_t gfx_egl_int;
typedef const unsigned char *(*gfx_gl_get_string_fn)(uint32_t);
typedef void (*gfx_proc_fn)(void);

typedef gfx_egl_display (*gfx_egl_get_platform_display_fn)(
    uint32_t, void *, const intptr_t *);
typedef gfx_egl_display (*gfx_egl_get_display_fn)(void *);
typedef gfx_egl_bool (*gfx_egl_initialize_fn)(gfx_egl_display,
                                              gfx_egl_int *,
                                              gfx_egl_int *);
typedef gfx_egl_bool (*gfx_egl_bind_api_fn)(uint32_t);
typedef gfx_egl_bool (*gfx_egl_choose_config_fn)(
    gfx_egl_display, const gfx_egl_int *, gfx_egl_config *,
    gfx_egl_int, gfx_egl_int *);
typedef gfx_egl_context (*gfx_egl_create_context_fn)(
    gfx_egl_display, gfx_egl_config, gfx_egl_context,
    const gfx_egl_int *);
typedef gfx_egl_bool (*gfx_egl_make_current_fn)(gfx_egl_display,
                                                void *, void *,
                                                gfx_egl_context);
typedef const char *(*gfx_egl_query_string_fn)(gfx_egl_display,
                                               gfx_egl_int);
typedef gfx_proc_fn (*gfx_egl_get_proc_fn)(const char *);

enum {
    GFX_EGL_PLATFORM_SURFACELESS_MESA = 0x31DD,
    GFX_EGL_OPENGL_API = 0x30A2,
    GFX_EGL_VENDOR = 0x3053,
    GFX_EGL_VERSION = 0x3054,
    GFX_EGL_SURFACE_TYPE = 0x3033,
    GFX_EGL_PBUFFER_BIT = 0x0001,
    GFX_EGL_RENDERABLE_TYPE = 0x3040,
    GFX_EGL_OPENGL_BIT = 0x0008,
    GFX_EGL_NONE = 0x3038,
    GFX_GL_VENDOR = 0x1F00,
    GFX_GL_RENDERER = 0x1F01,
    GFX_GL_VERSION = 0x1F02,
};

static int probe_gl(void)
{
    void *lib = dlopen("libEGL.so.1", RTLD_NOW);
    if (!lib) {
        printf("GFX_GL_FAIL dlopen: %s\n", dlerror());
        return 0;
    }
    gfx_egl_get_platform_display_fn get_platform =
        (gfx_egl_get_platform_display_fn)
        dlsym(lib, "eglGetPlatformDisplay");
    gfx_egl_get_display_fn get_display = (gfx_egl_get_display_fn)
        dlsym(lib, "eglGetDisplay");
    gfx_egl_initialize_fn initialize = (gfx_egl_initialize_fn)
        dlsym(lib, "eglInitialize");
    gfx_egl_bind_api_fn bind_api = (gfx_egl_bind_api_fn)
        dlsym(lib, "eglBindAPI");
    gfx_egl_choose_config_fn choose = (gfx_egl_choose_config_fn)
        dlsym(lib, "eglChooseConfig");
    gfx_egl_create_context_fn create_context =
        (gfx_egl_create_context_fn)dlsym(lib, "eglCreateContext");
    gfx_egl_make_current_fn make_current = (gfx_egl_make_current_fn)
        dlsym(lib, "eglMakeCurrent");
    gfx_egl_query_string_fn query = (gfx_egl_query_string_fn)
        dlsym(lib, "eglQueryString");
    gfx_egl_get_proc_fn get_proc = (gfx_egl_get_proc_fn)
        dlsym(lib, "eglGetProcAddress");
    if (!initialize || !bind_api || !choose || !create_context ||
        !make_current || !query || !get_proc) {
        printf("GFX_GL_FAIL EGL entry points missing\n");
        return 0;
    }
    gfx_egl_display display = NULL;
    if (get_platform)
        display = get_platform(GFX_EGL_PLATFORM_SURFACELESS_MESA,
                               (void *)0, NULL);
    if (!display && get_display)
        display = get_display((void *)0);
    if (!display) {
        printf("GFX_GL_FAIL no EGL display\n");
        return 0;
    }
    gfx_egl_int major = 0, minor = 0;
    if (!initialize(display, &major, &minor)) {
        printf("GFX_GL_FAIL eglInitialize\n");
        return 0;
    }
    printf("GFX_EGL_OK vendor=\"%s\" version=\"%s\"\n",
           query(display, GFX_EGL_VENDOR),
           query(display, GFX_EGL_VERSION));
    if (!bind_api(GFX_EGL_OPENGL_API)) {
        printf("GFX_GL_FAIL eglBindAPI\n");
        return 0;
    }
    const gfx_egl_int attribs[] = {
        GFX_EGL_SURFACE_TYPE, GFX_EGL_PBUFFER_BIT,
        GFX_EGL_RENDERABLE_TYPE, GFX_EGL_OPENGL_BIT,
        GFX_EGL_NONE,
    };
    gfx_egl_config config = NULL;
    gfx_egl_int num_configs = 0;
    if (!choose(display, attribs, &config, 1, &num_configs) ||
        num_configs < 1) {
        printf("GFX_GL_FAIL eglChooseConfig\n");
        return 0;
    }
    gfx_egl_context context =
        create_context(display, config, (gfx_egl_context)0, NULL);
    if (!context) {
        printf("GFX_GL_FAIL eglCreateContext\n");
        return 0;
    }
    if (!make_current(display, (void *)0, (void *)0, context)) {
        printf("GFX_GL_FAIL eglMakeCurrent\n");
        return 0;
    }
    gfx_gl_get_string_fn gl_get_string = (gfx_gl_get_string_fn)
        get_proc("glGetString");
    if (!gl_get_string) {
        printf("GFX_GL_FAIL glGetString unavailable\n");
        return 0;
    }
    const unsigned char *vendor = gl_get_string(GFX_GL_VENDOR);
    const unsigned char *renderer = gl_get_string(GFX_GL_RENDERER);
    const unsigned char *version = gl_get_string(GFX_GL_VERSION);
    if (!vendor || !renderer || !version) {
        printf("GFX_GL_FAIL GL strings unavailable\n");
        return 0;
    }
    printf("GFX_GL_OK vendor=\"%s\" renderer=\"%s\" version=\"%s\"\n",
           vendor, renderer, version);
    if (!strstr((const char *)renderer, "llvmpipe")) {
        printf("GFX_GL_FAIL renderer is not llvmpipe\n");
        return 0;
    }
    return 1;
}

int main(void)
{
    printf("GFX_PROBE_START\n");
    fflush(stdout);
    int vulkan_ok = probe_vulkan();
    fflush(stdout);
    int gl_ok = probe_gl();
    fflush(stdout);
    if (vulkan_ok && gl_ok) {
        printf("GFX_PROBE_OK\n");
        return 0;
    }
    printf("GFX_PROBE_FAIL vulkan=%d gl=%d\n", vulkan_ok, gl_ok);
    return 1;
}
