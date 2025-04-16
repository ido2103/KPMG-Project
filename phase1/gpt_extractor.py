import json
import logging

# Import config, clients, and helpers
from .config import logger, EXTRACTION_PROMPT, OPENAI_DEPLOYMENT
from .azure_clients import openai_client
from .document_analyzer import get_nearby_text

def extract_fields_with_gpt(ocr_result):
    """Use GPT-4o to extract fields from OCR results"""
    logger.info("Preparing OCR results for GPT processing...")
    # Prepare the input for GPT-4o using a more structured approach with layout information
    formatted_text = ""

    # Include the full document content
    if ocr_result.content:
        logger.info("Adding full document content...")
        formatted_text += f"Full Document Text:\n{ocr_result.content}\n\n"

    # Add enhanced layout extraction with bounding boxes and reading order
    formatted_text += "---- STRUCTURED CONTENT WITH LAYOUT INFO ----\n"

    for i, page in enumerate(ocr_result.pages):
        formatted_text += f"\n---- Page {i+1} ----\n"
        
        # Include page dimensions for context
        formatted_text += f"Page Dimensions: Width={page.width}, Height={page.height}\n\n"
        
        # Process selection marks (checkboxes) first - these are critical for form fields
        if hasattr(page, 'selection_marks') and page.selection_marks:
            formatted_text += "SELECTION MARKS (CHECKBOXES/RADIO BUTTONS):\n"
            for idx, mark in enumerate(page.selection_marks):
                # Get mark position safely
                position_str = "position unknown"
                try:
                    if hasattr(mark, 'polygon') and mark.polygon:
                        try:
                            # Try to get first point coordinates
                            if hasattr(mark.polygon[0], 'x') and hasattr(mark.polygon[0], 'y'):
                                position_str = f"[x={mark.polygon[0].x:.1f},y={mark.polygon[0].y:.1f}]"
                            elif isinstance(mark.polygon[0], (int, float)) and len(mark.polygon) >= 2:
                                # Flat array format
                                position_str = f"[x={mark.polygon[0]:.1f},y={mark.polygon[1]:.1f}]"
                        except (IndexError, AttributeError):
                            position_str = "position error"
                except Exception:
                    position_str = "position error"
                
                # Get mark state
                state = "SELECTED" if mark.state == "selected" else "UNSELECTED"
                
                # Get nearby text safely
                try:
                    # Use the imported get_nearby_text function
                    nearby_text = get_nearby_text(mark, page.lines, 100) 
                except Exception as e:
                    logger.warning(f"Error getting nearby text: {str(e)}")
                    nearby_text = ""
                
                formatted_text += f"Selection Mark {idx+1}: {state} at {position_str} - Nearby text: '{nearby_text}'\n"
            formatted_text += "\n"
        
        # Process lines with bounding box information for spatial context
        if page.lines:
            formatted_text += "TEXT LINES WITH POSITION:\n"
            for line_idx, line in enumerate(page.lines):
                # Get bounding box coordinates safely
                position_str = ""
                try:
                    if hasattr(line, 'polygon') and line.polygon and len(line.polygon) >= 4:
                        try:
                            # Try different polygon formats
                            try:
                                # Point objects with x,y attributes
                                x_coords = [point.x for point in line.polygon]
                                y_coords = [point.y for point in line.polygon]
                            except AttributeError:
                                # Flat array [x1, y1, x2, y2, ...]
                                if isinstance(line.polygon[0], (int, float)):
                                    x_coords = line.polygon[0::2]  # Even indices
                                    y_coords = line.polygon[1::2]  # Odd indices
                                else:
                                    # Unknown format, skip position
                                    raise ValueError("Unknown polygon format")
                            
                            # Calculate bounding box
                            left, top = min(x_coords), min(y_coords)
                            right, bottom = max(x_coords), max(y_coords)
                            position_str = f"[x={left:.1f},y={top:.1f},w={(right-left):.1f},h={(bottom-top):.1f}]"
                        except Exception:
                            # If any error in calculation, skip position info
                            pass
                except Exception:
                    # If any error, don't include position info
                    pass
                
                # Add line with or without position info
                if position_str:
                    formatted_text += f"Line {line_idx+1} {position_str}: '{line.content}'\n"
                else:
                    formatted_text += f"Line {line_idx+1}: '{line.content}'\n"

    # Add table content with structure preserved and cell positions
    if ocr_result.tables:
        formatted_text += "\n---- TABLES WITH STRUCTURE ----\n"
        for table_idx, table in enumerate(ocr_result.tables):
            formatted_text += f"\nTable {table_idx + 1}:\n"
            
            # Track row and column spans safely
            try:
                max_row = max(cell.row_index for cell in table.cells) if table.cells else 0
                max_col = max(cell.column_index for cell in table.cells) if table.cells else 0
                formatted_text += f"Table Dimensions: {max_row+1} rows x {max_col+1} columns\n"
            except Exception as e:
                logger.warning(f"Error calculating table dimensions: {str(e)}")
                formatted_text += "Table Dimensions: unknown\n"
            
            # Group cells by row with position information
            rows = {}
            for cell in table.cells:
                if cell.row_index not in rows:
                    rows[cell.row_index] = []
                
                # Add position information for each cell safely
                position_info = ""
                try:
                    if hasattr(cell, 'polygon') and cell.polygon:
                        try:
                            # Try different polygon formats
                            try:
                                # Point objects with x,y attributes
                                x_coords = [point.x for point in cell.polygon]
                                y_coords = [point.y for point in cell.polygon]
                            except AttributeError:
                                # Flat array [x1, y1, x2, y2, ...]
                                if isinstance(cell.polygon[0], (int, float)):
                                    x_coords = cell.polygon[0::2]  # Even indices
                                    y_coords = cell.polygon[1::2]  # Odd indices
                                else:
                                    # Unknown format, skip position
                                    raise ValueError("Unknown polygon format")
                            
                            left, top = min(x_coords), min(y_coords)
                            position_info = f"[x={left:.1f},y={top:.1f}]"
                        except Exception:
                            # If any error, don't include position
                            pass
                except Exception:
                    # If any error, don't include position
                    pass
                
                # Add span information - check for None values before comparison
                span_info = ""
                if hasattr(cell, 'row_span') and cell.row_span is not None and cell.row_span > 1:
                    span_info += f"rowspan={cell.row_span}"
                if hasattr(cell, 'column_span') and cell.column_span is not None and cell.column_span > 1:
                    span_info += f"colspan={cell.column_span}"
                
                # Combine position and content
                cell_info = f"{position_info} {span_info}: {cell.content}"
                rows[cell.row_index].append((cell.column_index, cell_info))
            
            # Print table in row/column format with position data
            for row_idx in sorted(rows.keys()):
                # Sort cells by column
                sorted_cells = sorted(rows[row_idx], key=lambda x: x[0])
                formatted_text += f"Row {row_idx}: " + " | ".join([f"Col {cell[0]}: {cell[1]}" for cell in sorted_cells]) + "\n"

    # Print the OCR payload that will be sent to the model
    logger.info("==== OCR PAYLOAD FOR MODEL ====")
    print("\n==== OCR PAYLOAD START ====")
    print(formatted_text[:1000] + "..." if len(formatted_text) > 1000 else formatted_text)
    print("==== OCR PAYLOAD END ====\n")
    
    # Fill in the prompt template with enhanced OCR information
    logger.info("Filling prompt template...")
    filled_prompt = EXTRACTION_PROMPT.format(ocr_content=formatted_text)

    # Call GPT-4o with JSON mode
    logger.info("Calling Azure OpenAI GPT-4o for field extraction...")
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are an AI assistant that extracts structured information from documents."},
                {"role": "user", "content": filled_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        # Parse the response
        logger.info("Parsing GPT response...")
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
    except Exception as e:
        logger.error(f"Error during GPT processing: {str(e)}", exc_info=True)
        raise 