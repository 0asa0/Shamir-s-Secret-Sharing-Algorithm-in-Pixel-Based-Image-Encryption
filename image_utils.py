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
    # Using RGBA where alpha channel stores our marker for 256 values
    img_array = np.zeros((original_shape[0], original_shape[1], 4), dtype=np.uint8)
    
    # Fill the image with share data
    for y in range(original_shape[0]):
        for x in range(original_shape[1]):
            pixel_idx = y * original_shape[1] + x
            if pixel_idx < len(share_data):
                r, g, b = share_data[pixel_idx]
                
                # Store marker bits in alpha channel (default 255 - fully opaque)
                # We only need 1 bit per channel to mark if value is 256
                alpha = 255
                
                # Convert values for storage in PNG
                # If value is 256, store as 0 but mark it in the alpha channel
                r_mod = r % 256
                g_mod = g % 256
                b_mod = b % 256
                
                # Mark if any channel had value 256 using specific bits in alpha
                if r == 256: alpha -= 1  # Subtract 1 for R channel
                if g == 256: alpha -= 2  # Subtract 2 for G channel
                if b == 256: alpha -= 4  # Subtract 4 for B channel
                
                img_array[y, x] = [r_mod, g_mod, b_mod, alpha]
    
    # Convert numpy array to PIL Image with alpha channel
    return Image.fromarray(img_array, 'RGBA')

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
            if len(img_array.shape) == 3 and img_array.shape[2] >= 3:  # RGB or RGBA image
                r, g, b = img_array[y, x][:3]  # Get first 3 channels (RGB)
                
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
            if progress_callback and processed_pixels % 500 == 0:  # Reduced frequency of updates
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
                        
                        # Check bits in alpha to detect 256 values
                        # Alpha values below 255 indicate 256 values in specific channels
                        if alpha < 255:
                            # Check if R channel had 256 (bit 0 is set)
                            if (255 - alpha) & 1:
                                r = 256 if r == 0 else r
                            
                            # Check if G channel had 256 (bit 1 is set)
                            if (255 - alpha) & 2:
                                g = 256 if g == 0 else g
                                
                            # Check if B channel had 256 (bit 2 is set)
                            if (255 - alpha) & 4:
                                b = 256 if b == 0 else b
                    
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
            if progress_callback and processed_pixels % 500 == 0:  # Reduced frequency of updates
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
