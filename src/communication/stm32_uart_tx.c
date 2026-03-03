/* STM32 UART transmission scaffold.
 * Replace HAL stubs with your board-specific implementation.
 */

#include <stdint.h>
#include <stddef.h>

int stm32_uart_send_tracks(const uint8_t *buf, size_t len)
{
    if (buf == 0 || len == 0) {
        return -1;
    }

    /* TODO: call HAL_UART_Transmit or DMA-based sender here. */
    return 0;
}
