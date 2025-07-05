# OpenTelemetry Migration Guide

**Last Updated:** 2025-01-27  
**Status:** Future Migration (Current: structlog + prometheus-fastapi-instrumentator)

## 1. Overview

This guide documents the migration path from our current observability stack (structlog + prometheus-fastapi-instrumentator + manual request ID correlation) to OpenTelemetry. The migration is designed to be **additive and low-risk**, preserving all existing functionality while adding distributed tracing capabilities.

## 2. Current Observability Stack

### 2.1. Current Implementation
```python
# Current logging with structlog (from core/logging.py)
import structlog
from fastapi_app.core.logging import get_logger, log_key_event

logger = get_logger(__name__)
logger.info("Retrieving contract", extra={"contract_id": 123})

# Key event logging with standardized schema
log_key_event(
    logger=logger,
    event="contract_detail_request",
    success=True,
    duration_ms=123.45,
    contract_id=123
)

# Current metrics with prometheus-fastapi-instrumentator
# Automatic HTTP metrics via middleware in main.py

# Current request ID correlation via RequestIDMiddleware
# Automatically binds request_id to structlog context using contextvars
# No manual request ID handling needed in services
```

### 2.2. Current Testing Approach
```python
# Current testing with pytest-mock and capsys
@pytest.mark.asyncio
async def test_contract_logging(client: AsyncClient, capsys):
    """Tests that structured logging works correctly."""
    response = await client.get("/contracts/details/123")
    
    # Capture stdout to check log output
    captured = capsys.readouterr()
    log_output = captured.out.strip().split("\n")
    
    # Parse JSON logs or handle human-readable format
    log_records = []
    for line in log_output:
        if line.strip():
            try:
                log_records.append(json.loads(line))
            except json.JSONDecodeError:
                # Handle human-readable format with regex parsing
                pass
    
    # Verify structured logging output
    assert any("contract_detail_request" in str(record) for record in log_records)
```

### 2.3. Current structlog Configuration
The application uses a centralized logging configuration in `core/logging.py`:

```python
# Current setup_logging function
def setup_logging(settings: Settings) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # For request_id
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

The migration will enhance this configuration to include OpenTelemetry context.

## 3. Migration Benefits

### 3.1. What OpenTelemetry Adds
- **Automatic distributed tracing** across HTTP calls, database queries, etc.
- **Rich context correlation** between traces, metrics, and logs
- **Automatic instrumentation** for HTTPX, SQLAlchemy, FastAPI
- **Industry-standard observability** protocols
- **Vendor-neutral** observability framework

### 3.2. What Stays the Same
- **All existing code** continues to work unchanged
- **All existing tests** continue to pass
- **Service layer logic** remains identical
- **Structured logging** with structlog continues
- **HTTP metrics** continue to work
- **Global exception handler** in main.py continues to work
- **RequestIDMiddleware** continues to provide request correlation

## 4. Migration Phases

### Phase 1: Add OpenTelemetry (Minimal Disruption)
**Goal:** Add OpenTelemetry with zero code changes to existing services

#### 4.1.4. Correlation ID Transition Strategy
**Current State:** Manual request ID correlation using `RequestIDMiddleware` and structlog context variables.

**Migration Approach:** Maintain backward compatibility while adding OpenTelemetry trace context.

```python
# Enhanced RequestIDMiddleware that supports both approaches
from opentelemetry import trace
from opentelemetry.trace import SpanKind

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Enhanced middleware that supports both manual request ID and OpenTelemetry trace context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a unique request ID (existing functionality)
        request_id = str(uuid.uuid4())
        
        # Set the request ID in the context variable (existing)
        request_id_contextvar.set(request_id)
        
        # Bind the request ID to structlog context (existing)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Add OpenTelemetry tracing (new)
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "http_request",
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.request_id": request_id,  # Link to existing request_id
            }
        ) as span:
            # Process the request
            response = await call_next(request)
            
            # Add response attributes
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.response_size", len(response.body) if response.body else 0)
            
            # Add request_id to response headers for frontend correlation
            response.headers["X-Request-ID"] = request_id
            
            return response
```

**Enhanced structlog Configuration with OpenTelemetry Context:**
```python
# Update setup_logging function to include OpenTelemetry context
def setup_logging_with_opentelemetry(settings: Settings) -> None:
    """Configure structlog with both request_id and OpenTelemetry trace context."""
    
    def add_trace_context(logger, method_name, event_dict):
        """Add OpenTelemetry trace context to log records."""
        # Keep existing request_id from contextvars
        if "request_id" not in event_dict:
            current_request_id = request_id_contextvar.get(None)
            if current_request_id:
                event_dict["request_id"] = current_request_id
        
        # Add OpenTelemetry trace context
        current_span = trace.get_current_span()
        if current_span:
            span_context = current_span.get_span_context()
            if span_context.is_valid:
                event_dict["trace_id"] = format(span_context.trace_id, "032x")
                event_dict["span_id"] = format(span_context.span_id, "016x")
                event_dict["trace_flags"] = format(span_context.trace_flags, "02x")
        
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # Existing request_id
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            add_trace_context,  # New: Add OpenTelemetry context
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

**Service Layer Integration:**
```python
# Service methods continue to work unchanged
class ContractDetailsService:
    def __init__(self, db_session: AsyncSession):
        self.logger = structlog.get_logger(__name__)
        self.tracer = trace.get_tracer(__name__)  # New: OpenTelemetry tracer
    
    async def get_contract_details(self, contract_id: int):
        # Existing logging continues to work
        self.logger.info("Retrieving contract", extra={"contract_id": contract_id})
        
        # New: Add OpenTelemetry span (optional in Phase 1)
        with self.tracer.start_as_current_span("get_contract_details") as span:
            span.set_attribute("contract_id", contract_id)
            
            # Existing business logic continues unchanged
            contract = await self._get_contract_with_items(contract_id)
            if not contract:
                return None
            
            return contract_details
```

**Frontend Correlation Strategy:**
```typescript
// Angular HTTP interceptor for correlation
@Injectable()
export class CorrelationInterceptor implements HttpInterceptor {
  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Extract request_id from response headers (existing pattern)
    return next.handle(req).pipe(
      tap((event: HttpEvent<any>) => {
        if (event instanceof HttpResponse) {
          const requestId = event.headers.get('X-Request-ID');
          if (requestId) {
            // Use request_id for correlation (existing pattern)
            this.logger.info('API response received', {
              request_id: requestId,
              status: event.status,
              url: event.url
            });
          }
        }
      })
    );
  }
}
```

**Benefits of This Approach:**
1. **Backward Compatibility:** All existing request_id correlation continues to work
2. **Gradual Enhancement:** OpenTelemetry trace context is added without breaking existing functionality
3. **Dual Context:** Logs contain both request_id (for existing tools) and trace_id/span_id (for OpenTelemetry)
4. **Frontend Continuity:** Frontend continues to use request_id for correlation
5. **Future Migration:** Can gradually migrate to pure OpenTelemetry trace context in later phases

#### 4.1.1. Install Dependencies
```bash
# Add to pyproject.toml (using PDM format)
[tool.pdm.dependencies]
opentelemetry-api = "^1.21.0"
opentelemetry-sdk = "^1.21.0"
opentelemetry-instrumentation-fastapi = "^0.42b0"
opentelemetry-instrumentation-httpx = "^0.42b0"
opentelemetry-instrumentation-sqlalchemy = "^0.42b0"
opentelemetry-exporter-otlp-proto-http = "^1.21.0"

# Install with PDM
pdm add opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-http
```

#### 4.1.2. Add Configuration to main.py
```python
# Add to app/backend/src/fastapi_app/main.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_opentelemetry():
    """Configure OpenTelemetry for the application."""
    # Set up trace provider
    trace.set_tracer_provider(TracerProvider())
    
    # Configure OTLP exporter (adjust URL as needed)
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4318/v1/traces"
    )
    
    # Add span processor
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrument HTTPX client
    HTTPXClientInstrumentor.instrument()
    
    # Instrument SQLAlchemy
    SQLAlchemyInstrumentor.instrument()

# Add to lifespan function in main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown events."""
    # Setup structured logging first (existing)
    setup_logging(settings)
    
    # Add OpenTelemetry setup (new)
    setup_opentelemetry()
    
    # ... rest of existing startup logic
```

#### 4.1.3. Update structlog Configuration
```python
# Update structlog configuration to work with OpenTelemetry
# Modify existing setup_logging function in core/logging.py
import structlog
from opentelemetry import trace

def setup_logging_with_opentelemetry(settings: Settings) -> None:
    """Configure structured logging for the application with OpenTelemetry integration."""
    # Configure structlog with OpenTelemetry context
    structlog.configure(
        processors=[
            # Add OpenTelemetry trace context
            structlog.processors.add_log_level,
            structlog.processors.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Add trace context from OpenTelemetry
            structlog.processors.CallsiteParameterAdder(
                parameters={
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            # Add OpenTelemetry trace and span IDs
            structlog.processors.CallsiteParameterAdder(
                parameters={
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            structlog.contextvars.merge_contextvars,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger to use structlog
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    root_logger.propagate = False
```

### Phase 2: Enhance with Custom Tracing (Optional)
**Goal:** Add custom spans to key business operations

#### 4.2.1. Add Custom Spans to Services
```python
# Example: Enhanced ContractDetailsService
from opentelemetry import trace

class ContractDetailsService:
    def __init__(self, db_session: AsyncSession, esi_type_service: ESITypeService):
        self.logger = structlog.get_logger(__name__)
        self.tracer = trace.get_tracer(__name__)
    
    async def get_contract_details(self, contract_id: int):
        with self.tracer.start_as_current_span("get_contract_details") as span:
            span.set_attribute("contract_id", contract_id)
            
            self.logger.info("Retrieving contract", extra={"contract_id": contract_id})
            
            # Existing code continues unchanged
            contract = await self._get_contract_with_items(contract_id)
            if not contract:
                return None
            
            # Add sub-spans for major operations
            with self.tracer.start_as_current_span("enhance_contract_items"):
                enhanced_items = await self._enhance_contract_items(contract.items)
            
            return contract_details
```

#### 4.2.2. Enhance Existing RequestIDMiddleware
```python
# Enhance existing RequestIDMiddleware in core/logging.py
from opentelemetry import trace

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Enhanced middleware that generates request_id and adds OpenTelemetry tracing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a unique request ID (existing functionality)
        request_id = str(uuid.uuid4())
        
        # Set the request ID in the context variable (existing)
        request_id_contextvar.set(request_id)
        
        # Bind the request ID to structlog context (existing)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Add OpenTelemetry tracing
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("http_request") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("request_id", request_id)
            
            # Process the request
            response = await call_next(request)
            
            span.set_attribute("http.status_code", response.status_code)
            return response
```

### Phase 3: Optimize and Advanced Features (Optional)
**Goal:** Fine-tune instrumentation and add advanced features

#### 4.3.3. Transition to Pure OpenTelemetry Trace Context (Optional)
**Goal:** Eventually migrate from manual request_id to pure OpenTelemetry trace context.

**When to Consider This Transition:**
- All observability tools support OpenTelemetry trace context
- Frontend has been updated to use OpenTelemetry
- Team is comfortable with OpenTelemetry concepts
- Performance requirements justify the optimization

**Migration Strategy:**
```python
# Phase 3: Pure OpenTelemetry approach
class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Pure OpenTelemetry middleware - no manual request_id needed.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "http_request",
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
            }
        ) as span:
            # Process the request
            response = await call_next(request)
            
            # Add response attributes
            span.set_attribute("http.status_code", response.status_code)
            
            # Add trace context to response headers for frontend
            span_context = span.get_span_context()
            response.headers["X-Trace-ID"] = format(span_context.trace_id, "032x")
            response.headers["X-Span-ID"] = format(span_context.span_id, "016x")
            
            return response
```

**Updated structlog Configuration:**
```python
# Pure OpenTelemetry structlog configuration
def setup_logging_pure_opentelemetry(settings: Settings) -> None:
    """Configure structlog to use only OpenTelemetry trace context."""
    
    def add_trace_context(logger, method_name, event_dict):
        """Add OpenTelemetry trace context to log records."""
        current_span = trace.get_current_span()
        if current_span:
            span_context = current_span.get_span_context()
            if span_context.is_valid:
                event_dict["trace_id"] = format(span_context.trace_id, "032x")
                event_dict["span_id"] = format(span_context.span_id, "016x")
                event_dict["trace_flags"] = format(span_context.trace_flags, "02x")
        
        return event_dict

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            add_trace_context,  # Only OpenTelemetry context
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

**Frontend Migration:**
```typescript
// Angular HTTP interceptor using OpenTelemetry trace context
@Injectable()
export class OpenTelemetryInterceptor implements HttpInterceptor {
  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return next.handle(req).pipe(
      tap((event: HttpEvent<any>) => {
        if (event instanceof HttpResponse) {
          const traceId = event.headers.get('X-Trace-ID');
          const spanId = event.headers.get('X-Span-ID');
          
          if (traceId && spanId) {
            this.logger.info('API response received', {
              trace_id: traceId,
              span_id: spanId,
              status: event.status,
              url: event.url
            });
          }
        }
      })
    );
  }
}
```

**Benefits of Pure OpenTelemetry:**
1. **Standard Compliance:** Follows OpenTelemetry standards completely
2. **Vendor Neutrality:** Works with any OpenTelemetry-compatible backend
3. **Advanced Features:** Full access to distributed tracing capabilities
4. **Performance:** Optimized for OpenTelemetry tooling
5. **Future-Proof:** Aligns with industry standards

**Migration Considerations:**
- Requires updating all observability tools to use trace_id instead of request_id
- Frontend must be updated to handle OpenTelemetry trace context
- Existing log analysis tools may need updates
- Consider running both approaches in parallel during transition

#### 4.3.1. Custom Metrics with OpenTelemetry
```python
# Migrate custom metrics to OpenTelemetry
from opentelemetry import metrics

# Replace prometheus custom metrics
contract_requests = metrics.get_meter(__name__).create_counter(
    "contract_requests_total",
    description="Total contract requests"
)

# Usage in service
contract_requests.add(1, {"endpoint": "details", "status": "success"})
```

#### 4.3.2. Advanced Correlation
```python
# Enhanced correlation between traces and logs
from opentelemetry import trace

def log_with_trace_context(logger, message, **kwargs):
    """Log with automatic trace context correlation."""
    current_span = trace.get_current_span()
    if current_span:
        span_context = current_span.get_span_context()
        kwargs["trace_id"] = format(span_context.trace_id, "032x")
        kwargs["span_id"] = format(span_context.span_id, "016x")
    
    logger.info(message, **kwargs)
```

## 5. Testing Strategy

### 5.1. Existing Tests (No Changes Required)
```python
# All existing tests continue to work unchanged
# Example from test_observability.py
@pytest.mark.asyncio
async def test_successful_request_logs_key_event(client: AsyncClient, capsys):
    """Tests that a successful API call generates structured log events."""
    response = await client.get("/contracts/")
    assert response.status_code == 200

    captured = capsys.readouterr()
    log_output = captured.out.strip().split("\n")
    
    # Parse log records (existing pattern)
    log_records = []
    for line in log_output:
        if line.strip():
            try:
                log_records.append(json.loads(line))
            except json.JSONDecodeError:
                # Handle human-readable format (existing pattern)
                if "contract_search_executed" in line:
                    # Parse using existing regex patterns
                    pass
    
    # These assertions continue to work
    assert any("contract_search_executed" in str(record) for record in log_records)
```

### 5.2. New OpenTelemetry Tests (Addition Only)
```python
# New tests for OpenTelemetry features
@pytest.mark.asyncio
async def test_trace_correlation(client: AsyncClient):
    """Test that traces correlate with logs."""
    # Test implementation would depend on OpenTelemetry testing setup
    pass

@pytest.mark.asyncio
async def test_span_attributes(client: AsyncClient):
    """Test that spans have correct attributes."""
    # Test implementation would depend on OpenTelemetry testing setup
    pass
```

### 5.3. Integration Testing
```python
# Test end-to-end correlation
@pytest.mark.asyncio
async def test_end_to_end_correlation(client: AsyncClient):
    """Test that request IDs correlate across frontend/backend."""
    # Test that frontend request ID appears in backend traces and logs
    pass
```

## 6. Migration Checklist

### 6.1. Pre-Migration
- [ ] Document current observability metrics
- [ ] Identify key business operations for custom tracing
- [ ] Set up OpenTelemetry collector/backend
- [ ] Plan testing strategy for new capabilities

### 6.2. Phase 1 Implementation
- [ ] Install OpenTelemetry dependencies
- [ ] Add configuration to main.py
- [ ] Update structlog configuration
- [ ] Test that existing functionality works
- [ ] Verify automatic instrumentation

### 6.3. Phase 2 Implementation
- [ ] Add custom spans to key services
- [ ] Enhance HTTP interceptors with tracing
- [ ] Add tracing-specific tests
- [ ] Document new tracing capabilities

### 6.4. Phase 3 Implementation
- [ ] Migrate custom metrics to OpenTelemetry
- [ ] Implement advanced correlation features
- [ ] Optimize instrumentation performance
- [ ] Add comprehensive tracing tests

## 7. Rollback Strategy

### 7.1. Quick Rollback
```python
# Disable OpenTelemetry instrumentation
# Comment out setup_opentelemetry() call in main.py
# Revert structlog configuration if needed
```

### 7.2. Gradual Rollback
```python
# Disable specific instrumentations
# FastAPIInstrumentor.uninstrument_app(app)
# HTTPXClientInstrumentor.uninstrument()
# SQLAlchemyInstrumentor.uninstrument()
```

## 8. Performance Considerations

### 8.1. Overhead
- **Automatic instrumentation**: ~1-5% overhead
- **Custom spans**: Minimal overhead
- **Batch processing**: Reduces network overhead

### 8.2. Optimization
```python
# Optimize span sampling for high-traffic endpoints
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# Sample only 10% of requests in high-traffic scenarios
sampler = TraceIdRatioBased(0.1)
trace.set_tracer_provider(TracerProvider(sampler=sampler))
```

## 9. Monitoring and Validation

### 9.1. Migration Validation
- [ ] Verify all existing tests pass
- [ ] Check that logs still contain expected information
- [ ] Validate metrics are still being collected
- [ ] Test request ID correlation still works

### 9.2. New Capabilities Validation
- [ ] Verify traces are being generated
- [ ] Check span attributes are correct
- [ ] Validate correlation between traces and logs
- [ ] Test distributed tracing across services

## 10. Documentation Updates

### 10.1. Update Observability Guide
- [ ] Update `02-observability-guide.md` with OpenTelemetry patterns
- [ ] Add OpenTelemetry testing strategies
- [ ] Update AI implementation patterns

### 10.2. Update Observability Spec
- [ ] Update `observability-spec.md` with OpenTelemetry requirements
- [ ] Add frontend OpenTelemetry integration patterns
- [ ] Update correlation strategies

## 11. Future Considerations

### 11.1. Frontend Integration
- [ ] Add OpenTelemetry to Angular frontend
- [ ] Implement end-to-end trace correlation
- [ ] Add frontend-specific tracing patterns

### 11.2. Advanced Features
- [ ] Implement trace sampling strategies
- [ ] Add custom span processors
- [ ] Implement trace-based alerting
- [ ] Add performance profiling capabilities

---

## 12. AI Implementation Prompts

### 12.1. Phase 1 Setup
```
"Add OpenTelemetry to our FastAPI application with structlog integration. 
Install required dependencies using PDM, add configuration to main.py lifespan 
function, and ensure existing observability continues to work. 
Use the migration guide at design/fastapi/guides/03-observability-opentelemetry-migration.md 
for reference. Note: We use PDM for dependency management, not Poetry."
```

### 12.2. Phase 2 Enhancement
```
"Add custom OpenTelemetry spans to our ContractDetailsService. 
Follow the patterns in the migration guide and ensure all existing 
functionality continues to work. Add appropriate span attributes 
for contract_id and operation type. Note: The service already uses 
structlog logging - integrate OpenTelemetry tracing with existing 
log_key_event calls."
```

### 12.3. Testing
```
"Add OpenTelemetry-specific tests to our observability test suite. 
Follow the testing patterns in the migration guide and ensure 
existing tests continue to pass. Test trace correlation and span attributes."
```

---

**Note:** This migration guide is designed to be used by Cursor when implementing OpenTelemetry. The phased approach ensures minimal risk and maximum compatibility with existing code.
