package vn.goldenpath.platform.tenant;

import javax.sql.DataSource;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class TenantDataSourceConfig {

  /** Wraps the application DataSource (not Flyway's, which connects as the owner). */
  @Bean
  static BeanPostProcessor tenantDataSourceWrapper() {
    return new BeanPostProcessor() {
      @Override
      public Object postProcessAfterInitialization(Object bean, String beanName) {
        if ("dataSource".equals(beanName)
            && bean instanceof DataSource ds
            && !(bean instanceof TenantAwareDataSource)) {
          return new TenantAwareDataSource(ds);
        }
        return bean;
      }
    };
  }
}
