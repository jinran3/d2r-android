// 设备上的 Vulkan 实况：加载器版本、实例扩展、每个物理设备的驱动名、API 版本与子组大小。
// The live Vulkan situation on the device: loader version, instance extensions, and the driver name, API version and subgroup size of every physical device.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

static void version_text(uint32_t version, char *out, size_t cap) {
    snprintf(out, cap, "%u.%u.%u", (version >> 22) & 0x7f, (version >> 12) & 0x3ff, version & 0xfff);
}

static void report_device(VkPhysicalDevice device) {
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(device, &properties);
    char api[32], driver[32];
    version_text(properties.apiVersion, api, sizeof api);
    version_text(properties.driverVersion, driver, sizeof driver);
    printf("  name=%s type=%u api=%s driver=%s vendor=%#x device=%#x\n", properties.deviceName,
           (unsigned)properties.deviceType, api, driver, properties.vendorID, properties.deviceID);
    printf("  maxImageDimension2D=%u maxComputeWorkGroupInvocations=%u maxPushConstants=%u maxBoundDescriptorSets=%u\n",
           properties.limits.maxImageDimension2D, properties.limits.maxComputeWorkGroupInvocations,
           properties.limits.maxPushConstantsSize, properties.limits.maxBoundDescriptorSets);

    // 子组大小：着色器按 64 子组构建，必须与真机一致。
    // Subgroup size: the shaders are built for 64-wide subgroups and must match the device.
    VkPhysicalDeviceSubgroupProperties subgroup;
    memset(&subgroup, 0, sizeof subgroup);
    subgroup.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_PROPERTIES;
    VkPhysicalDeviceProperties2 properties2;
    memset(&properties2, 0, sizeof properties2);
    properties2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;
    properties2.pNext = &subgroup;
    vkGetPhysicalDeviceProperties2(device, &properties2);
    printf("  subgroupSize=%u supportedOperations=%#x supportedStages=%#x\n", subgroup.subgroupSize,
           subgroup.supportedOperations, subgroup.supportedStages);

    uint32_t device_extensions = 0;
    vkEnumerateDeviceExtensionProperties(device, NULL, &device_extensions, NULL);
    VkExtensionProperties *device_list = calloc(device_extensions ? device_extensions : 1, sizeof *device_list);
    vkEnumerateDeviceExtensionProperties(device, NULL, &device_extensions, device_list);
    printf("  device extensions %u:", device_extensions);
    for (uint32_t i = 0; i < device_extensions; i++) printf(" %s", device_list[i].extensionName);
    printf("\n");
    free(device_list);

    uint32_t families = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(device, &families, NULL);
    VkQueueFamilyProperties *queues = calloc(families ? families : 1, sizeof *queues);
    vkGetPhysicalDeviceQueueFamilyProperties(device, &families, queues);
    for (uint32_t q = 0; q < families; q++)
        printf("  queue family %u count=%u flags=%#x\n", q, queues[q].queueCount, queues[q].queueFlags);
    free(queues);

    VkPhysicalDeviceMemoryProperties memories;
    vkGetPhysicalDeviceMemoryProperties(device, &memories);
    for (uint32_t m = 0; m < memories.memoryTypeCount; m++)
        printf("  memory type %u heap=%u size=%llu flags=%#x\n", m, memories.memoryTypes[m].heapIndex,
               (unsigned long long)memories.memoryHeaps[memories.memoryTypes[m].heapIndex].size,
               memories.memoryTypes[m].propertyFlags);
}

int main(void) {
    const char *icd = getenv("VK_ICD_FILENAMES");
    printf("VK_ICD_FILENAMES=%s\n", icd ? icd : "(unset)");
    uint32_t loader = 0;
    if (vkEnumerateInstanceVersion(&loader) == VK_SUCCESS) {
        char text[32]; version_text(loader, text, sizeof text);
        printf("loader instance version %s\n", text);
    } else {
        printf("loader instance version unavailable (Vulkan 1.0 loader)\n");
    }
    uint32_t count = 0;
    if (vkEnumerateInstanceExtensionProperties(NULL, &count, NULL) != VK_SUCCESS) {
        printf("cannot query instance extensions\n"); return 1;
    }
    VkExtensionProperties *properties = calloc(count ? count : 1, sizeof *properties);
    vkEnumerateInstanceExtensionProperties(NULL, &count, properties);
    printf("instance extensions %u:", count);
    for (uint32_t i = 0; i < count; i++) printf(" %s", properties[i].extensionName);
    printf("\n");
    free(properties);

    VkApplicationInfo application = {VK_STRUCTURE_TYPE_APPLICATION_INFO};
    application.pApplicationName = "dm-vulkan-probe";
    application.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo create = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    create.pApplicationInfo = &application;
    VkInstance instance = VK_NULL_HANDLE;
    VkResult result = vkCreateInstance(&create, NULL, &instance);
    if (result != VK_SUCCESS) { printf("vkCreateInstance failed: %d\n", (int)result); return 1; }
    uint32_t devices = 0;
    vkEnumeratePhysicalDevices(instance, &devices, NULL);
    printf("physical devices %u\n", devices);
    VkPhysicalDevice *list = calloc(devices ? devices : 1, sizeof *list);
    vkEnumeratePhysicalDevices(instance, &devices, list);
    for (uint32_t i = 0; i < devices; i++) {
        printf(" [%u]\n", i);
        report_device(list[i]);
    }
    free(list);
    vkDestroyInstance(instance, NULL);
    return devices ? 0 : 2;
}
