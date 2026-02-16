import json
from pathlib import Path
import networkx as nx

### Data Preprocessing and formatting functionality

class ICD11Processor:
    """Process and format ICD11 data from JSON files."""
    
    def __init__(self, input_filepath):
        """
        Initialize the processor with an input file.
        
        Args:
            input_filepath: Path to the input JSON file
        """
        self.input_filepath = input_filepath
        self.data = {}
        self.Formatted_data = {}
    
    def load_data(self):
        """Load data from the input JSON file."""
        with open(self.input_filepath) as f:
            self.data = json.load(f)
        print(f"Loaded {len(self.data)} records")
        return self
    
    @staticmethod
    def extract_values(ICD11_values):
        """
        Extract and normalize values from a dictionary structure.
        
        Args:
            ICD11_values: Dictionary containing ICD11 entry data
            
        Returns:
            Dictionary with normalized values
        """
        ICD11_subset = {
            'id': ICD11_values.get('@id'),
            'parent': ICD11_values.get('parent', ''),
            'child': ICD11_values.get('child', ''),
            'title': ICD11_values.get('title', {}).get('@value', ''),
            'def': ICD11_values.get('definition', {}).get('@value', ''),
            'synonyms': []
        }
        
        syns = ICD11_values.get('synonym')
        if syns:
            ICD11_subset['synonyms'] = [
                syn.get('label', {}).get('@value', '')
                for syn in syns
                if syn.get('label', {}).get('@value')
            ]
        
        return ICD11_subset
    
    def process(self):
        """Process the loaded data and create Formatted_data dictionary."""
        self.Formatted_data = {}
        for k, v in self.data.items():
            ICD11_subset = self.extract_values(v)
            entry_id = ICD11_subset.get('id')
            if entry_id:
                self.Formatted_data[entry_id] = ICD11_subset
        
        print(f"Processed {len(self.Formatted_data)} entries")
        return self
    
    def save(self, output_filepath='./data/FormattedICD11.json'):
        """
        Save the processed data to a JSON file.
        
        Args:
            output_filepath: Path to the output JSON file
        """
        # Create directory if it doesn't exist
        Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_filepath, 'w') as file:
            json.dump(self.Formatted_data, file, indent=4)
        
        print(f"Saved to {output_filepath}")
        return self
    
    def run(self, output_filepath='./data/FormattedICD11.json'):
        """
        Run the complete pipeline: load, process, and save.
        
        Args:
            output_filepath: Path to the output JSON file
        """
        self.load_data().process().save(output_filepath)
        return self.Formatted_data




class ICD11HierarchyBuilder:
    def __init__(self, ICD11):
        self.ICD11 = ICD11
        self.UUIDs = set()
        self.Data = {}
    
    def extract_uid(self, url):
        """Extract UUID from URL by taking the last segment."""
        return url.rsplit('/', 1)[-1]
    
    def extract_uids(self, urls):
        """Extract UIDs from a list of URLs, returning empty list if None."""
        return [self.extract_uid(url) for url in urls] if urls else []
    
    def build(self):
        for k, v in self.ICD11.items():
            uid = self.extract_uid(k)
            self.UUIDs.add(uid)
            self.Data[uid] = {
                'title': v.get('title'),
                'def': v.get('def'),
                'synonyms': v.get('synonyms'),
                'parents': self.extract_uids(v.get('parent')),
                'children': self.extract_uids(v.get('child'))
            }
    
    def save(self):
        with open('./data/ICD11_Hierarchy.json', 'w') as file:
            json.dump(self.Data, file, indent=4)





## Graph Traversal Operations
############################

class ICD11GraphBuilder:
    def __init__(self, ICD11_Hierarchy):
        self.ICD11_Hierarchy = ICD11_Hierarchy
        self.G = None
    
    def build(self):
        self.G = nx.DiGraph()
        for node_id, data in self.ICD11_Hierarchy.items():
            self.G.add_node(
                node_id,
                title=data.get('title', ''),
                definition=data.get('def', ''),
                synonyms=data.get('synonyms', [])
            )
            
            for child_id in data.get('children', []):
                self.G.add_edge(node_id, child_id)
        
        return self
    
    def get_children_with_info(self, target_title):
        """Find nodes by title and return children with their attributes"""
        if self.G is None:
            raise ValueError("Graph not built. Call build() first.")
        
        results = {}
        
        for node_id in self.G.nodes():
            title = self.G.nodes[node_id].get('title', '')
            
            if title == target_title:
                children_info = []
                for child_id in self.G.successors(node_id):
                    children_info.append({
                        'id': child_id,
                        'title': self.G.nodes[child_id].get('title', 'N/A'),
                        'definition': self.G.nodes[child_id].get('definition', 'N/A'),
                        'synonyms': self.G.nodes[child_id].get('synonyms', [])
                    })
                
                results = {
                    'parent_id': node_id,
                    'parent_title': title,
                    'children': children_info
                }
        
        return results
    
    def get_all_descendants_by_title(self, target_title):
        """Find nodes by title and return ALL descendants (not just direct children)"""
        if self.G is None:
            raise ValueError("Graph not built. Call build() first.")
        
        results = {}
        
        for node_id in self.G.nodes():
            title = self.G.nodes[node_id].get('title', '')
            
            if title == target_title:
                all_descendants = nx.descendants(self.G, node_id)
                direct_children = list(self.G.successors(node_id))
                
                results = {
                    'node_id': node_id,
                    'title': title,
                    'direct_children': direct_children,
                    'all_descendants': list(all_descendants),
                    'direct_children_count': len(direct_children),
                    'total_descendants_count': len(all_descendants)
                }
        
        return results


