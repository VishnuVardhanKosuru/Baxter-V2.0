/**
 * @name Resolved Call Graph
 * @description Extracts the call graph with fully resolved callee signatures
 *              including the callee's return type — for mock setup in tests.
 * @kind table
 * @id java/call-graph
 */
import java

from MethodCall mc
where mc.getCaller().fromSource()
  and not mc.getCaller().getDeclaringType() instanceof AnonymousClass
select
  mc.getCaller().getDeclaringType().getQualifiedName()  as caller_class,
  mc.getCaller().getName()                              as caller_method,
  mc.getCallee().getDeclaringType().getQualifiedName()  as callee_class,
  mc.getCallee().getName()                              as callee_method,
  mc.getCallee().getReturnType().toString()             as callee_return_type,
  mc.getLocation().getStartLine()                       as call_line
