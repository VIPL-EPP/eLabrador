# Installation

## PaddleOCR
You need to install [PaddlePaddle](https://www.paddlepaddle.org.cn/install/quick?docurl=/documentation/docs/zh/install/pip/linux-pip.html) and [PaddleOCR 2.6](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.6/doc/doc_en/quickstart_en.md). 
Additionally, you will need to manually install cuDNN (please refer to online tutorials for specific installation steps).

## PyKDL

1. In some cases, `PyKDL` might be missing after installing `tf2_ros`. If this happens, install it using Conda:

```sh
conda install python-orocos-kdl -c conda-forge
```

---

# Configuration

The configuration parameters are as follows:

1. **Camera Intrinsics:** `fx`, `fy`, `cx`, `cy`, `height`, and `width`.
2. **Control Topic:** The topic used to control the module's execution state, along with the expected string message required to activate it.
3. **Specific Settings:** Language settings, GPU usage flag (`use_gpu`), output topic names, etc.

> **Note:** If you want to enable visualization for the detection results, you must download the font file [simfang.ttf](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.6/doc/fonts/simfang.ttf) and place it in the `scripts` directory.

---

# Implementation Details

## Control Mechanism

You can activate the OCR module by publishing the expected string message to the configured control topic. If any unexpected string is received on this topic, the OCR module will shut down and remain in standby mode until the correct activation message is received again.

## Output Format

The module publishes a custom `HeaderString` message.

* **Header:** The `stamp` is synchronized with the corresponding RGB image, and the `frame_id` is set to the VIO global coordinate system (`world`).
* **String Payload:** This contains a decodable JSON string. Once decoded, it parses as a list where each element is a 5-tuple. The structure of the tuple is as follows:
1. `x` coordinate
2. `y` coordinate
3. `z` coordinate
4. Detected `text` (string)
5. `Confidence` score (float, ranging from 0 to 1)

