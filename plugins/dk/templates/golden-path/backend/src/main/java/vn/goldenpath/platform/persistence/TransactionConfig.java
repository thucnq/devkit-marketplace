package vn.goldenpath.platform.persistence;

import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Transactions are the outermost advice so that @Audited (lowest precedence) runs inside the
 * business transaction: a rolled-back change never leaves an audit row behind.
 */
@Configuration(proxyBeanMethods = false)
@EnableTransactionManagement(proxyTargetClass = true, order = Ordered.HIGHEST_PRECEDENCE + 100)
class TransactionConfig {}
