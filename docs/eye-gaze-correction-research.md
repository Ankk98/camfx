# Eye Gaze Correction - Research & Implementation Options

## Executive Summary

After researching eye gaze correction implementations, we found several viable approaches:

1. **✅ MediaPipe Face Mesh with Iris Landmarks** - Already available in our dependencies
2. **✅ Open-source GitHub projects** - Reference implementations available
3. **⚠️ Commercial tools** - Not directly usable but provide insights
4. **⚠️ Deep learning approaches** - More complex, may require additional dependencies

**Recommendation**: Start with MediaPipe Face Mesh iris landmarks + simple warping techniques. This is feasible with existing dependencies.

---

## 1. MediaPipe Capabilities

### MediaPipe Face Mesh with Iris Landmarks ✅

**Status**: Already available in MediaPipe 0.10.0 (our current version)

**What it provides:**
- 468 facial landmarks (with `refine_landmarks=True`)
- **Iris landmarks**: Left and right iris centers and contours
- Real-time performance
- No additional dependencies needed

**Code Example:**
```python
import mediapipe as mp
import cv2

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,  # Enables iris landmarks
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Process frame
results = face_mesh.process(frame_rgb)

if results.multi_face_landmarks:
    face_landmarks = results.multi_face_landmarks[0]
    
    # Iris landmarks are included in the 468 landmarks
    # Left iris center: landmark 468
    # Right iris center: landmark 473
    # (Exact indices may vary - need to verify)
    
    # Access iris landmarks
    left_iris = face_landmarks.landmark[468]  # Left iris center
    right_iris = face_landmarks.landmark[473]  # Right iris center
```

**Iris Landmark Connections:**
- `FACEMESH_LEFT_IRIS` - Left iris connections
- `FACEMESH_RIGHT_IRIS` - Right iris connections
- `FACEMESH_IRISES` - Both irises

**Advantages:**
- ✅ Already in our dependencies
- ✅ Real-time performance
- ✅ Accurate iris detection
- ✅ No additional setup required

**Limitations:**
- ⚠️ Provides iris position, not gaze direction
- ⚠️ Need to calculate gaze direction from iris position relative to eye socket

---

## 2. Open-Source Implementations

### GitHub: Eye-Contact-RealTime-Detection

**Repository**: `arnaudlvq/Eye-Contact-RealTime-Detection`  
**Language**: Python  
**Dependencies**: OpenCV, MediaPipe  
**Status**: Active project

**What it does:**
- Detects eye contact status (looking at camera or not)
- Uses MediaPipe Face Mesh for landmark detection
- Calculates gaze direction from iris position
- Provides GUI for real-time detection

**Key Insights:**
- Uses iris landmarks to determine if eyes are looking at camera
- Calculates angle between iris center and eye socket center
- Can be adapted for gaze correction (not just detection)

**Implementation Approach:**
1. Detect iris center using MediaPipe
2. Calculate eye socket center from facial landmarks
3. Determine gaze direction from iris position
4. Warp eye region to simulate looking at camera

**Feasibility**: ✅ High - Uses same dependencies we have

---

## 3. Technical Implementation Approaches

### Approach 1: Simple Eye Warping (Recommended for MVP)

**Complexity**: Medium  
**Performance**: Good (~20-30ms per frame)  
**Dependencies**: MediaPipe Face Mesh, OpenCV

**Steps:**
1. **Detect iris position** using MediaPipe Face Mesh
2. **Calculate desired iris position** (center of eye socket for "looking at camera")
3. **Extract eye region** (left and right eyes separately)
4. **Warp eye region** using affine transformation or thin-plate spline
5. **Blend warped eyes** back into frame

**Warping Techniques:**
- **Affine Transformation**: Simple, fast, but less natural
- **Thin-Plate Spline (TPS)**: More natural, better for eye warping
- **Mesh-based warping**: Most natural, but more complex

**OpenCV Functions:**
```python
# Affine transformation
M = cv2.getAffineTransform(src_points, dst_points)
warped = cv2.warpAffine(eye_region, M, (w, h))

# Thin-plate spline (requires additional library or custom implementation)
# Or use cv2.remap() with custom mapping
```

**Advantages:**
- ✅ Uses existing dependencies
- ✅ Real-time feasible
- ✅ Natural-looking results possible

**Challenges:**
- ⚠️ Need to handle edge cases (blinking, side glances)
- ⚠️ Must preserve eye shape and texture
- ⚠️ Smooth transitions between frames

---

### Approach 2: Deep Learning Gaze Redirection

**Complexity**: High  
**Performance**: Moderate-High (depends on model)  
**Dependencies**: PyTorch/TensorFlow, pre-trained models

**Examples:**
- **Gaze Redirection Networks**: Academic research models
- **GAN-based approaches**: Generate realistic eye images
- **Transformer-based**: More recent, better quality

**Pre-trained Models:**
- Some research models available on GitHub
- May require model conversion (PyTorch → ONNX → TensorFlow Lite)
- Model sizes: 10-100MB typically

**Advantages:**
- ✅ Most natural-looking results
- ✅ Can handle extreme gaze angles
- ✅ Better preservation of eye appearance

**Disadvantages:**
- ❌ Requires additional dependencies (PyTorch/TensorFlow)
- ❌ Larger model size
- ❌ Higher computational cost
- ❌ More complex integration

**Recommendation**: Defer to Phase 3+ if simple warping doesn't meet quality requirements.

---

## 4. Implementation Strategy

### Phase 1: Basic Eye Contact Detection (Quick Win)

**Goal**: Detect if user is looking at camera

**Implementation:**
```python
class EyeContactDetector:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            refine_landmarks=True,
            max_num_faces=1
        )
    
    def is_looking_at_camera(self, frame, threshold=0.1):
        """Returns True if eyes are looking at camera."""
        results = self.face_mesh.process(frame)
        if not results.multi_face_landmarks:
            return None
        
        # Calculate iris position relative to eye socket
        # If iris is centered in socket, user is looking at camera
        # Implementation details...
        
        return is_centered
```

**Use Case**: Provide feedback to user ("Look at camera!")

---

### Phase 2: Simple Eye Warping (MVP)

**Goal**: Subtle eye correction for small gaze deviations

**Implementation:**
1. Detect iris position
2. Calculate correction needed (small adjustments only)
3. Apply subtle warping to eye region
4. Blend smoothly

**Limitations:**
- Works best for small gaze deviations (< 15 degrees)
- May have artifacts for extreme angles
- Requires careful blending

**Code Structure:**
```python
class EyeGazeCorrection:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            refine_landmarks=True
        )
    
    def correct_gaze(self, frame, strength=0.5):
        """
        Corrects eye gaze to appear looking at camera.
        
        Args:
            frame: Input frame
            strength: Correction strength (0.0-1.0)
        """
        # 1. Get iris landmarks
        # 2. Calculate desired position
        # 3. Warp eye regions
        # 4. Blend back
        return corrected_frame
```

---

### Phase 3: Advanced Warping (Future)

**Goal**: Handle larger gaze angles with better quality

**Approaches:**
- Thin-plate spline warping
- Mesh-based deformation
- Deep learning models (if needed)

---

## 5. Libraries and Tools

### Available Libraries

#### 1. MediaPipe (Already Have) ✅
- Face Mesh with iris landmarks
- Real-time performance
- No additional setup

#### 2. OpenCV (Already Have) ✅
- Image warping functions
- Affine transformations
- Blending operations

#### 3. scikit-image (Optional)
- Thin-plate spline implementation
- Advanced image transformations
- **Installation**: `pip install scikit-image`

#### 4. dlib (Optional)
- Face landmark detection (alternative to MediaPipe)
- More detailed facial feature detection
- **Installation**: `pip install dlib`
- **Note**: MediaPipe is sufficient, dlib is redundant

#### 5. PyTorch/TensorFlow (Future)
- For deep learning approaches
- Only if simple warping insufficient

---

## 6. Reference Projects

### 1. Eye-Contact-RealTime-Detection
- **GitHub**: `arnaudlvq/Eye-Contact-RealTime-Detection`
- **Language**: Python
- **Dependencies**: OpenCV, MediaPipe
- **Use**: Reference for detection logic

### 2. Gaze Redirection Research
- Various academic implementations
- Most require PyTorch/TensorFlow
- Good for understanding advanced techniques

---

## 7. Recommended Implementation Plan

### Step 1: Eye Contact Detection (1-2 days)
- Implement basic detection using MediaPipe iris landmarks
- Calculate if user is looking at camera
- Add to CLI as `camfx detect-eye-contact --preview`

### Step 2: Simple Eye Warping (3-5 days)
- Implement basic affine transformation for eye warping
- Handle left and right eyes separately
- Add smooth blending
- Test with various gaze angles

### Step 3: Refinement (2-3 days)
- Improve warping quality
- Handle edge cases (blinking, extreme angles)
- Optimize performance
- Add CLI command: `camfx gaze-correct --strength 0.5`

### Step 4: Advanced (Future)
- Consider thin-plate spline if needed
- Evaluate deep learning models if quality insufficient

---

## 8. Code Example: Basic Implementation

```python
import cv2
import numpy as np
import mediapipe as mp

class EyeGazeCorrection:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        # Iris landmark indices (need to verify exact indices)
        self.LEFT_IRIS_CENTER = 468
        self.RIGHT_IRIS_CENTER = 473
    
    def get_eye_region(self, frame, landmarks, eye_indices):
        """Extract eye region from frame."""
        h, w = frame.shape[:2]
        eye_points = np.array([
            [int(landmarks.landmark[i].x * w), 
             int(landmarks.landmark[i].y * h)]
            for i in eye_indices
        ])
        x, y, w_eye, h_eye = cv2.boundingRect(eye_points)
        return frame[y:y+h_eye, x:x+w_eye], (x, y, w_eye, h_eye)
    
    def warp_eye_to_center(self, eye_region, iris_pos, eye_center, strength=0.5):
        """Warp eye region to center iris."""
        # Calculate translation needed
        dx = (eye_center[0] - iris_pos[0]) * strength
        dy = (eye_center[1] - iris_pos[1]) * strength
        
        # Apply affine transformation
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        h, w = eye_region.shape[:2]
        warped = cv2.warpAffine(eye_region, M, (w, h))
        return warped
    
    def apply(self, frame, strength=0.5):
        """Apply gaze correction to frame."""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if not results.multi_face_landmarks:
            return frame
        
        face_landmarks = results.multi_face_landmarks[0]
        h, w = frame.shape[:2]
        
        # Get iris positions
        left_iris = face_landmarks.landmark[self.LEFT_IRIS_CENTER]
        right_iris = face_landmarks.landmark[self.RIGHT_IRIS_CENTER]
        
        # Get eye regions and warp
        # (Implementation details for extracting and warping eyes)
        
        return corrected_frame
```

---

## 9. Performance Considerations

### Processing Time Estimates

| Approach | Processing Time | Quality |
|----------|----------------|---------|
| Detection only | ~5ms | N/A (just detection) |
| Simple affine warping | ~20-30ms | Good for small angles |
| Thin-plate spline | ~30-50ms | Better quality |
| Deep learning | ~50-100ms | Best quality |

### Optimization Strategies

1. **Process every N frames**: Warp every 2-3 frames, interpolate
2. **Reduce resolution**: Process at lower res, upscale result
3. **GPU acceleration**: Use MediaPipe GPU delegate (if available)
4. **Frame skipping**: Skip correction during blinking

---

## 10. Conclusion

### Feasibility: ✅ **HIGH**

**With Existing Dependencies:**
- ✅ MediaPipe Face Mesh provides iris landmarks
- ✅ OpenCV provides warping functions
- ✅ Can implement basic gaze correction

**Recommended Approach:**
1. Start with simple affine transformation warping
2. Use MediaPipe iris landmarks for detection
3. Implement gradual correction (not full redirection)
4. Add as optional effect with strength parameter

**Additional Dependencies (Optional):**
- `scikit-image` for thin-plate spline (better quality)
- Only add if simple warping insufficient

**Implementation Time:**
- Basic version: 1 week
- Polished version: 2-3 weeks

**Recommendation**: Implement as Phase 2 feature after current effects are stable. Start with detection, then add correction.

---

## References

1. MediaPipe Face Mesh: https://google.github.io/mediapipe/solutions/face_mesh.html
2. MediaPipe Iris: https://google.github.io/mediapipe/solutions/iris.html
3. Eye-Contact-RealTime-Detection: https://github.com/arnaudlvq/Eye-Contact-RealTime-Detection
4. OpenCV Warping: https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html

