#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        printf("devices=%lu default=%s\n", (unsigned long)devices.count, device ? device.name.UTF8String : "<nil>");
        if (!device || devices.count == 0) return 10;
        if (argc > 1 && strcmp(argv[1], "--enumerate") == 0) return 0;
        NSError *error = nil;
        NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\nkernel void probe(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i * i + 42; }";
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        if (!library) { fprintf(stderr, "compile: %s\n", error.localizedDescription.UTF8String ?: "<unknown>"); return 11; }
        id<MTLFunction> function = [library newFunctionWithName:@"probe"];
        if (!function) return 12;
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function error:&error];
        if (!pipeline) { fprintf(stderr, "pipeline: %s\n", error.localizedDescription.UTF8String ?: "<unknown>"); return 13; }
        NSUInteger count = 1024;
        id<MTLBuffer> output = [device newBufferWithLength:count * sizeof(uint32_t) options:MTLResourceStorageModeShared];
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLCommandBuffer> buffer = [queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [buffer computeCommandEncoder];
        if (!output || !queue || !buffer || !encoder) return 14;
        [encoder setComputePipelineState:pipeline];
        [encoder setBuffer:output offset:0 atIndex:0];
        [encoder dispatchThreads:MTLSizeMake(count, 1, 1) threadsPerThreadgroup:MTLSizeMake(pipeline.threadExecutionWidth, 1, 1)];
        [encoder endEncoding];
        [buffer commit];
        [buffer waitUntilCompleted];
        if (buffer.status != MTLCommandBufferStatusCompleted) {
            fprintf(stderr, "execute: %s\n", buffer.error.localizedDescription.UTF8String ?: "<unknown>");
            return 15;
        }
        const uint32_t *values = output.contents;
        for (uint32_t i = 0; i < count; i++) if (values[i] != i * i + 42) return 16;
        printf("computed and verified %lu GPU results\n", (unsigned long)count);
        if (argc > 1 && strcmp(argv[1], "--shared-event") == 0) {
            id<MTLSharedEvent> event = [device newSharedEvent];
            if (!event) { fprintf(stderr, "shared event unavailable\n"); return 17; }
            id<MTLCommandBuffer> signal = [queue commandBuffer];
            [signal encodeSignalEvent:event value:42];
            [signal commit];
            [signal waitUntilCompleted];
            if (signal.status != MTLCommandBufferStatusCompleted || event.signaledValue != 42) return 18;
            puts("GPU shared event signaled value 42");
        }
        return 0;
    }
}
