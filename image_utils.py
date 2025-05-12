import numpy as np
from PIL import Image
import base64
import io
from sss_core import split_secret, recover_secret, PRIME
import time

def create_preview_image(share_data, original_shape):
    """
    Create a preview image from share data
    """
    if len(share_data[0]) != 3:  # Check if we have R,G,B channels
        raise ValueError("Expected share data with 3 channels")
    
    # Create an empty image with the same shape as the original
    img_array = np.zeros(original_shape, dtype=np.uint8)
    
    # We'll create a separate array to mark which pixels had values of 256
    # This helps us distinguish between original 0 and values that were 256
    marker_array = np.zeros((original_shape[0], original_shape[1], 3), dtype=np.uint8)
    
    # Fill the image with share data
    for y in range(original_shape[0]):
        for x in range(original_shape[1]):
            pixel_idx = y * original_shape[1] + x
            if pixel_idx < len(share_data):
                r, g, b = share_data[pixel_idx]
                
                # Check for values that are exactly 256 (would become 0 in the PNG)
                # We'll use a special encoding: 255 in the main image and 1 in the marker
                r_is_256 = 1 if r == 256 else 0
                g_is_256 = 1 if g == 256 else 0
                b_is_256 = 1 if b == 256 else 0
                
                # Store markers for any 256 values
                marker_array[y, x] = [r_is_256, g_is_256, b_is_256]
                
                # Convert 256 to 255 in the main image
                r_val = 255 if r == 256 else r % 256
                g_val = 255 if g == 256 else g % 256
                b_val = 255 if b == 256 else b % 256
                
                img_array[y, x] = [r_val, g_val, b_val]
    
    # Combine the arrays: we'll use the alpha channel for our marker
    # Convert RGB to RGBA
    rgba_array = np.zeros((original_shape[0], original_shape[1], 4), dtype=np.uint8)
    rgba_array[:, :, :3] = img_array  # Copy RGB channels
    
    # Use the alpha channel as our marker: 254 means normal, 255 means there was a 256
    # This gives us a way to detect which pixels were originally 256
    rgba_array[:, :, 3] = 254  # Default alpha
    
    # Set special alpha values for pixels that had 256 in any channel
    for y in range(original_shape[0]):
        for x in range(original_shape[1]):
            if np.any(marker_array[y, x] > 0):
                # Encode the marker in the alpha channel
                # We use 255, 253, 252 to indicate which channel(s) had 256
                if marker_array[y, x, 0] == 1 and marker_array[y, x, 1] == 0 and marker_array[y, x, 2] == 0:
                    rgba_array[y, x, 3] = 255  # R only
                elif marker_array[y, x, 0] == 0 and marker_array[y, x, 1] == 1 and marker_array[y, x, 2] == 0:
                    rgba_array[y, x, 3] = 253  # G only
                elif marker_array[y, x, 0] == 0 and marker_array[y, x, 1] == 0 and marker_array[y, x, 2] == 1:
                    rgba_array[y, x, 3] = 252  # B only
                elif marker_array[y, x, 0] == 1 and marker_array[y, x, 1] == 1 and marker_array[y, x, 0] == 0:
                    rgba_array[y, x, 3] = 251  # R and G
                elif marker_array[y, x, 0] == 1 and marker_array[y, x, 1] == 0 and marker_array[y, x, 2] == 1:
                    rgba_array[y, x, 3] = 250  # R and B
                elif marker_array[y, x, 0] == 0 and marker_array[y, x, 1] == 1 and marker_array[y, x, 2] == 1:
                    rgba_array[y, x, 3] = 249  # G and B
                elif marker_array[y, x, 0] == 1 and marker_array[y, x, 1] == 1 and marker_array[y, x, 2] == 1:
                    rgba_array[y, x, 3] = 248  # All three channels
    
    # Convert numpy array to PIL Image with alpha channel
    return Image.fromarray(rgba_array, 'RGBA')

def image_to_shares(image, num_shares, threshold, progress_callback=None):
    """
    Convert an image to Shamir's Secret Sharing shares
    
    Args:
        image: PIL Image object
        num_shares: Total number of shares to generate
        threshold: Minimum number of shares needed to reconstruct
        progress_callback: Function to call with progress updates (0.0-1.0)
        
    Returns:
        tuple: (shares_data, share_preview_images)
            - shares_data: List of lists, each containing the y values for all pixels in the image
            - share_preview_images: List of PIL Image objects for preview
    """
    # Convert image to numpy array for processing
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    
    # Create storage for shares
    shares_data = [[] for _ in range(num_shares)]
    
    # Total number of pixels for progress tracking
    total_pixels = height * width
    processed_pixels = 0
    
    # Process each pixel
    for y in range(height):
        for x in range(width):
            # Get pixel values
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:  # RGB image
                r, g, b = img_array[y, x]
                
                # Split each color channel
                r_shares = split_secret(int(r), threshold, num_shares)
                g_shares = split_secret(int(g), threshold, num_shares)
                b_shares = split_secret(int(b), threshold, num_shares)
                
                # Store the y values in the corresponding share
                for i in range(num_shares):
                    shares_data[i].append((r_shares[i][1], g_shares[i][1], b_shares[i][1]))
            
            else:  # Grayscale image
                pixel = img_array[y, x]
                
                # Split the grayscale value
                pixel_shares = split_secret(int(pixel), threshold, num_shares)
                
                # Store the y values
                for i in range(num_shares):
                    # Duplicate the value to create RGB
                    value = pixel_shares[i][1]
                    shares_data[i].append((value, value, value))
            
            # Update progress
            processed_pixels += 1
            if progress_callback and processed_pixels % 100 == 0:
                progress_callback(processed_pixels / total_pixels)
    
    # Create preview images for each share
    share_preview_images = []
    for share_data in shares_data:
        share_img = create_preview_image(share_data, (height, width, 3))
        share_preview_images.append(share_img)
    
    # Final progress update
    if progress_callback:
        progress_callback(1.0)
    
    return shares_data, share_preview_images

def shares_to_image(shares, progress_callback=None):
    """
    Reconstruct an image from its shares
    
    Args:
        shares: List of tuples (index, PIL Image)
        progress_callback: Function to call with progress updates (0.0-1.0)
        
    Returns:
        PIL Image: Reconstructed image
    """
    if not shares:
        raise ValueError("No shares provided")
    
    # Get dimensions from the first share
    _, first_share = shares[0]
    width, height = first_share.size
    
    # Extract share data from images
    share_data = []
    for idx, share_img in shares:
        # Convert image to numpy array
        img_array = np.array(share_img)
        
        # Extract pixel data
        pixels = []
        for y in range(height):
            for x in range(width):
                if len(img_array.shape) >= 3:  # RGB or RGBA image
                    r, g, b = img_array[y, x][:3]  # Get RGB values
                    
                    # Check if this image has an alpha channel (our marker channel)
                    if img_array.shape[2] == 4:
                        alpha = img_array[y, x, 3]
                        
                        # Decode our special alpha values to restore 256 values
                        if alpha == 255:  # R channel was 256
                            r = 256 if r == 255 else r
                        elif alpha == 253:  # G channel was 256
                            g = 256 if g == 255 else g
                        elif alpha == 252:  # B channel was 256
                            b = 256 if b == 255 else b
                        elif alpha == 251:  # R and G were 256
                            r = 256 if r == 255 else r
                            g = 256 if g == 255 else g
                        elif alpha == 250:  # R and B were 256
                            r = 256 if r == 255 else r
                            b = 256 if b == 255 else b
                        elif alpha == 249:  # G and B were 256
                            g = 256 if g == 255 else g
                            b = 256 if b == 255 else b
                        elif alpha == 248:  # All three were 256
                            r = 256 if r == 255 else r
                            g = 256 if g == 255 else g
                            b = 256 if b == 255 else b
                    
                    pixels.append((r, g, b))
                else:  # Grayscale image
                    value = img_array[y, x]
                    pixels.append((value, value, value))
        
        share_data.append((idx, pixels))
    
    # Create reconstructed image array
    reconstructed = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Total number of pixels for progress tracking
    total_pixels = height * width
    processed_pixels = 0
    
    # Process each pixel position
    for y in range(height):
        for x in range(width):
            pixel_idx = y * width + x
            
            # Gather shares for this pixel
            r_shares = []
            g_shares = []
            b_shares = []
            
            for idx, pixels in share_data:
                if pixel_idx < len(pixels):
                    r, g, b = pixels[pixel_idx]
                    r_shares.append((idx, r))
                    g_shares.append((idx, g))
                    b_shares.append((idx, b))
            
            # Recover the original RGB values
            try:
                r = recover_secret(r_shares)
                g = recover_secret(g_shares)
                b = recover_secret(b_shares)
                
                # Ensure values are within 0-255 range for final image
                r = min(255, r % 256)
                g = min(255, g % 256)
                b = min(255, b % 256)
                
                reconstructed[y, x] = [r, g, b]
            except Exception as e:
                # If recovery fails, set to black
                reconstructed[y, x] = [0, 0, 0]
            
            # Update progress
            processed_pixels += 1
            if progress_callback and processed_pixels % 100 == 0:
                progress_callback(processed_pixels / total_pixels)
    
    # Final progress update
    if progress_callback:
        progress_callback(1.0)
    
    # Convert numpy array to PIL Image
    return Image.fromarray(reconstructed)

def download_button(object_to_download, download_filename, button_text):
    """
    Generate a link to download the given object.
    
    Args:
        object_to_download: The object to be downloaded (file or bytes)
        download_filename: Filename to download as
        button_text: Text to display on the download button
        
    Returns:
        HTML string containing the download link
    """
    try:
        # If object is a file or bytes-like object
        b64 = base64.b64encode(object_to_download).decode()
    except AttributeError:
        # If object is a string
        b64 = base64.b64encode(object_to_download.encode()).decode()
    
    button_uuid = str(id(button_text))
    button_id = f"download-button-{button_uuid}"
    
    custom_css = f"""
        <style>
            #{button_id} {{
                background-color: #d90429;
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 5px;
                border: none;
                text-decoration: none;
                font-size: 0.9rem;
                text-align: center;
                display: inline-block;
                margin: 0.25rem 0;
                cursor: pointer;
                transition: background-color 0.3s;
            }}
            #{button_id}:hover {{
                background-color: #ef233c;
            }}
        </style>
    """
    
    download_link = custom_css + f"""
        <a id="{button_id}" href="data:application/octet-stream;base64,{b64}" download="{download_filename}">{button_text}</a>
    """
    
    return download_link
