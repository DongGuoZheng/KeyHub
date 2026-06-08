#pragma once
#include "Kismet/BlueprintFunctionLibrary.h"
#include "KeyHubAuthLibrary.generated.h"

UCLASS()
class KEYHUB_API UKeyHubAuthLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /**
     * Get the current device's unique MAC address identifier.
     * Pure function — can be used as input to Verify/Register nodes.
     * @return MAC address string, e.g. "AA-BB-CC-DD-EE-FF"
     */
    UFUNCTION(BlueprintPure, Category = "KeyHub|Device")
    static FString GetDeviceUniqueID();
};
