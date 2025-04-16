import logging

# Import Azure client and logger
from .azure_clients import document_intelligence_client
from .config import logger # Use the configured logger


def analyze_document(file_path):
    """Analyze a document using Azure Document Intelligence with prebuilt-layout"""
    logger.info(f"Analyzing document at path: {file_path}...")
    try:
        with open(file_path, "rb") as f:
            logger.info("Sending document to Azure Document Intelligence...")
            poller = document_intelligence_client.begin_analyze_document(
                "prebuilt-layout",
                body=f,
                content_type="application/octet-stream"
            )
        
        logger.info("Waiting for analysis to complete...")
        result = poller.result()
        logger.info(f"Document analysis complete. Found {len(result.pages)} pages.")
        return result
    except Exception as e:
        logger.error(f"Error during document analysis: {str(e)}", exc_info=True)
        raise

def get_nearby_text(element, lines, proximity_radius):
    """Find text that is spatially close to a given element (like a checkbox)"""
    if not hasattr(element, 'polygon') or not element.polygon:
        return ""
    
    # Get the center point of the element
    # Handle different polygon formats (some might be direct coordinates rather than Point objects)
    try:
        # First attempt: try accessing as Point objects with x,y attributes
        x_coords = [point.x for point in element.polygon]
        y_coords = [point.y for point in element.polygon]
    except AttributeError:
        # Alternative format: might be [x1, y1, x2, y2, ...] flat array or other format
        # Try to handle various formats that Azure Document Intelligence might return
        try:
            if isinstance(element.polygon, list) and len(element.polygon) >= 2:
                if isinstance(element.polygon[0], (int, float)):
                    # Handle flat array [x1, y1, x2, y2, ...]
                    x_coords = element.polygon[0::2]  # Get even indices (0, 2, 4...)
                    y_coords = element.polygon[1::2]  # Get odd indices (1, 3, 5...)
                elif hasattr(element.polygon[0], 'x') and hasattr(element.polygon[0], 'y'):
                    # Handle list of objects with x,y props
                    x_coords = [point.x for point in element.polygon]
                    y_coords = [point.y for point in element.polygon]
                else:
                    # Can't determine format, use default position
                    logger.warning(f"Unknown polygon format: {element.polygon}")
                    return ""
            else:
                # Can't determine format, use default position
                logger.warning(f"Unknown polygon format: {element.polygon}")
                return ""
        except Exception as e:
            logger.warning(f"Error processing polygon: {str(e)}")
            return ""
    
    # Calculate center point
    center_x = sum(x_coords) / len(x_coords)
    center_y = sum(y_coords) / len(y_coords)
    
    nearby_lines = []
    
    for line in lines:
        if not hasattr(line, 'polygon') or not line.polygon:
            continue
        
        # Get center of the line, handling different polygon formats  
        try:
            # First attempt: try accessing as Point objects with x,y attributes
            line_x_coords = [point.x for point in line.polygon]
            line_y_coords = [point.y for point in line.polygon]
        except AttributeError:
            # Alternative format: try different polygon representations
            try:
                if isinstance(line.polygon, list) and len(line.polygon) >= 2:
                    if isinstance(line.polygon[0], (int, float)):
                        # Handle flat array [x1, y1, x2, y2, ...]
                        line_x_coords = line.polygon[0::2]  # Get even indices
                        line_y_coords = line.polygon[1::2]  # Get odd indices
                    elif hasattr(line.polygon[0], 'x') and hasattr(line.polygon[0], 'y'):
                        # Handle list of objects with x,y props
                        line_x_coords = [point.x for point in line.polygon]
                        line_y_coords = [point.y for point in line.polygon]
                    else:
                        # Skip if format can't be determined
                        continue
                else:
                    # Skip if format can't be determined
                    continue
            except Exception:
                # Skip this line if there's any error
                continue
                
        # Calculate center point of line
        line_center_x = sum(line_x_coords) / len(line_x_coords)
        line_center_y = sum(line_y_coords) / len(line_y_coords)
        
        # Calculate distance
        distance = ((center_x - line_center_x) ** 2 + (center_y - line_center_y) ** 2) ** 0.5
        
        # If within radius, add to nearby lines
        if distance <= proximity_radius:
            nearby_lines.append((distance, line.content))
    
    # Sort by distance and join the closest 3 lines
    nearby_lines.sort(key=lambda x: x[0])
    return " | ".join([line[1] for line in nearby_lines[:3]])

def get_element_center(element):
    """Get the center coordinates of an element's polygon safely"""
    if not hasattr(element, 'polygon') or not element.polygon:
        return None
    
    try:
        # Handle different polygon formats
        try:
            # Point objects with x,y attributes
            x_coords = [point.x for point in element.polygon]
            y_coords = [point.y for point in element.polygon]
        except AttributeError:
            # Flat array [x1, y1, x2, y2, ...]
            if isinstance(element.polygon, list) and len(element.polygon) >= 2:
                if isinstance(element.polygon[0], (int, float)):
                    x_coords = element.polygon[0::2]  # Even indices
                    y_coords = element.polygon[1::2]  # Odd indices
                else:
                    return None
            else:
                return None
        
        # Calculate center
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        return (center_x, center_y)
    except Exception:
        return None 