# Troubleshooting Guide

## Common Issues and Solutions

### Ollama Connection Issues

**Problem**: `Ollama health check failed: Connection refused`

**Solutions**:
1. Ensure Ollama is running:
   ```bash
   ollama serve
   ```

2. Check if Ollama is listening on the correct port:
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. Verify `.env` has correct `OLLAMA_BASE_URL`:
   ```
   OLLAMA_BASE_URL=http://localhost:11434
   ```

4. If using a different host/port, update the URL accordingly

---

### Docker Not Available

**Problem**: `Code execution unavailable - Docker service is not running`

**Solutions**:
1. Start Docker daemon:
   ```bash
   # Linux
   sudo systemctl start docker
   
   # macOS
   open -a Docker
   
   # Windows
   # Start Docker Desktop
   ```

2. Verify Docker is running:
   ```bash
   docker ps
   ```

3. Build the sandbox image if not exists:
   ```bash
   docker build -t kai-python-sandbox:latest -f docker/Dockerfile .
   ```

4. For improved security, install gVisor (optional):
   ```bash
   # Linux
   wget https://storage.googleapis.com/gvisor/releases/release/latest/runsc
   chmod +x runsc
   sudo mv runsc /usr/local/bin
   
   # Configure Docker to use runsc runtime
   ```

---

### Database Errors

**Problem**: `sqlite3.OperationalError: database is locked`

**Solutions**:
1. Only one process should access the database at a time
2. Check for zombie processes:
   ```bash
   ps aux | grep python
   kill <pid>
   ```

3. Remove lock file if stale:
   ```bash
   rm ./data/kai.db-journal
   ```

4. Ensure `SQLITE_DB_PATH` in `.env` points to a writable location

**Problem**: `LanceDB error: Table not found`

**Solutions**:
1. Initialize vector store:
   ```bash
   rm -rf ./data/lancedb  # Careful! This deletes all memories
   # Restart Kai to reinitialize
   ```

2. Ensure `VECTOR_DB_PATH` directory exists and is writable:
   ```bash
   mkdir -p ./data/lancedb
   chmod 755 ./data/lancedb
   ```

---

### Memory/RAG Issues

**Problem**: `Failed to initialize MemoryStoreTool: encryption_key not found`

**Solutions**:
1. Generate encryption key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Add to `.env`:
   ```
   ENCRYPTION_KEY=your_generated_key_here
   ```

**Problem**: Memory retrieval returns no results

**Solutions**:
1. Verify memories were stored:
   ```python
   # In Python shell
   from src.storage.vector_store import VectorStore
   vs = VectorStore("./data/lancedb")
   table = vs.get_user_memory_table()
   print(table.to_pandas())
   ```

2. Check embedding provider is configured:
   - With OpenRouter API key: Uses remote embeddings
   - Without API key: Uses mock embeddings (limited functionality)
   - Configure `OPENROUTER_API_KEY` in `.env` for production use

---

### OpenRouter/External Model Issues

**Problem**: `OpenRouter health check failed: HTTP 401`

**Solutions**:
1. Verify API key in `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

2. Check API key is valid at https://openrouter.ai/keys

3. Ensure sufficient credits in your OpenRouter account

**Problem**: `Rate limit exceeded`

**Solutions**:
1. Wait for rate limit to reset (typically 1 minute)
2. Reduce query frequency
3. System will automatically fall back to local model

---

### Web Search Issues

**Problem**: `DuckDuckGo search failed: Rate limit`

**Solutions**:
1. Wait 1-2 minutes before retrying
2. System will automatically use cached results if available
3. Reduce search frequency

**Problem**: `No results found`

**Solutions**:
1. Refine query to be more specific
2. Check internet connection
3. Try alternative search terms

---

### Sentiment Analysis Warnings

**Warning**: `vaderSentiment not available, using mock fallback`

**Solutions**:
1. Install VADER:
   ```bash
   pip install vaderSentiment
   ```

2. Verify installation:
   ```bash
   python -c "from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer; print('OK')"
   ```

3. The mock fallback is functional but less accurate - keyword-based emotion detection

---

### Cost Tracking Issues

**Problem**: Cost limits not working

**Solutions**:
1. Verify `.env` settings:
   ```
   DEFAULT_COST_LIMIT=1.0
   SOFT_CAP_THRESHOLD=0.8
   ```

2. Check current cost:
   ```
   You: /cost
   ```

3. Reset cost tracker if needed:
   ```python
   # In Python shell
   from src.core.orchestrator import Orchestrator
   # orchestrator.cost_tracker.reset()
   ```

---

### Performance Issues

**Problem**: Slow response times (>5 seconds)

**Solutions**:
1. Check which model is being used (external models are slower)
2. Monitor with `/cost` - may be waiting for rate limits
3. Reduce context window in `config/models.yaml`
4. Verify Ollama is running locally (not remote)

**Problem**: High memory usage

**Solutions**:
1. Clear conversation history:
   ```bash
   rm ./data/kai.db
   ```

2. Reduce vector store size:
   ```bash
   rm -rf ./data/lancedb
   ```

3. Adjust `max_history` in metrics collector

---

### Configuration Issues

**Problem**: `Config file not found: config/models.yaml`

**Solutions**:
1. Create config directory:
   ```bash
   mkdir -p config
   ```

2. Copy example configs:
   ```bash
   cp config/models.yaml.example config/models.yaml
   cp config/tools.yaml.example config/tools.yaml
   ```

3. Edit with your settings

**Problem**: `Invalid YAML syntax`

**Solutions**:
1. Validate YAML:
   ```bash
   python -c "import yaml; yaml.safe_load(open('config/models.yaml'))"
   ```

2. Check indentation (use spaces, not tabs)
3. Ensure values are properly quoted

---

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'src'`

**Solutions**:
1. Install in development mode:
   ```bash
   pip install -e .
   ```

2. Ensure you're in the project root directory
3. Verify Python path:
   ```bash
   python -c "import sys; print(sys.path)"
   ```

---

## Getting Help

If issues persist:

1. **Enable debug logging**:
   Edit `src/lib/logger.py` to set level="DEBUG"

2. **Check logs**:
   Logs are printed to console by default

3. **Verify installation**:
   ```bash
   pip list | grep -E "langgraph|ollama|lancedb|docker"
   ```

4. **System info**:
   ```bash
   python --version
   docker --version
   ollama --version
   ```

5. **Create an issue** with:
   - Error message (full stack trace)
   - Python version
   - OS and version
   - Steps to reproduce
   - Relevant configuration (redact API keys!)

---

## Performance Optimization

### For Faster Responses

1. **Use local models for simple queries**:
   - Ensure `granite3.1:2b` is configured in `models.yaml`
   - Set appropriate complexity thresholds

2. **Pre-build Docker image**:
   ```bash
   docker build -t kai-python-sandbox:latest -f docker/Dockerfile .
   ```

3. **Optimize embeddings**:
   - Use smaller embedding model if memory constrained
   - Adjust `top_k` in memory searches

### For Lower Costs

1. **Increase soft cap threshold**:
   ```
   SOFT_CAP_THRESHOLD=0.7  # Switch to local earlier
   ```

2. **Use structured JSON I/O**:
   - Already implemented for external models
   - Reduces token usage significantly

3. **Monitor costs**:
   ```
   You: /cost
   ```

---

## Advanced Debugging

### Enable SQL Logging

```python
# In src/storage/sqlite_store.py
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Monitor Docker Containers

```bash
# List running containers
docker ps

# View logs
docker logs <container_id>

# Inspect resource usage
docker stats
```

### Profile Performance

```bash
python -m cProfile -o profile.stats -m src.cli.main
python -m pstats profile.stats
```

---

## Clean Reset

If all else fails, start fresh:

```bash
# Backup data (optional)
cp -r ./data ./data.backup

# Clean all state
rm -rf ./data
rm -rf ~/.cache/huggingface  # If embedding issues

# Rebuild
pip install -e .
docker build -t kai-python-sandbox:latest -f docker/Dockerfile .

# Restart services
ollama serve &
python -m src.cli.main
```
