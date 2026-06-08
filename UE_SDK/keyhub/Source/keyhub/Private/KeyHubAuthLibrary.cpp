#include "KeyHubAuthLibrary.h"

#if PLATFORM_WINDOWS
#include <Windows.h>
#include <iphlpapi.h>
#pragma comment(lib, "iphlpapi.lib")
#endif

FString UKeyHubAuthLibrary::GetDeviceUniqueID()
{
#if PLATFORM_WINDOWS
    // Retrieve MAC address of the first network adapter
    IP_ADAPTER_INFO AdapterInfo[16];
    DWORD dwBufLen = sizeof(AdapterInfo);
    if (GetAdaptersInfo(AdapterInfo, &dwBufLen) == NO_ERROR)
    {
        PIP_ADAPTER_INFO pInfo = AdapterInfo;
        if (pInfo && pInfo->AddressLength == 6)
        {
            return FString::Printf(TEXT("%02X-%02X-%02X-%02X-%02X-%02X"),
                pInfo->Address[0], pInfo->Address[1], pInfo->Address[2],
                pInfo->Address[3], pInfo->Address[4], pInfo->Address[5]);
        }
    }
    return FString();
#else
    return FPlatformMisc::GetDeviceId();
#endif
}
