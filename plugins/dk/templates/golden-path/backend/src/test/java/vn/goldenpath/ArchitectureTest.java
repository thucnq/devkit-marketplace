package vn.goldenpath;

import static com.tngtech.archunit.base.DescribedPredicate.alwaysTrue;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.simpleNameEndingWith;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noFields;
import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS;
import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_USE_JAVA_UTIL_LOGGING;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import java.time.LocalDateTime;
import org.springframework.beans.factory.annotation.Autowired;

/** Architecture rules enforced on every build (see spring-conventions). */
@AnalyzeClasses(packages = "vn.goldenpath", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

  @ArchTest
  static final ArchRule platformDoesNotDependOnFeatures =
      noClasses()
          .that()
          .resideInAPackage("..platform..")
          .should()
          .dependOnClassesThat()
          .resideInAPackage("..feature..");

  @ArchTest
  static final ArchRule controllersDoNotUseRepositories =
      noClasses()
          .that()
          .resideInAPackage("..feature..")
          .and()
          .haveSimpleNameEndingWith("Controller")
          .should()
          .dependOnClassesThat()
          .haveSimpleNameEndingWith("Repository");

  @ArchTest
  static final ArchRule featuresTalkThroughServicesOnly =
      slices()
          .matching("vn.goldenpath.feature.(*)..")
          .should()
          .notDependOnEachOther()
          .ignoreDependency(alwaysTrue(), simpleNameEndingWith("Service"))
          .ignoreDependency(alwaysTrue(), resideInAPackage("..dto.."));

  @ArchTest
  static final ArchRule noFieldInjection =
      noFields().should().beAnnotatedWith(Autowired.class).because("use constructor injection");

  @ArchTest
  static final ArchRule instantsNotLocalDateTime =
      noFields()
          .that()
          .areDeclaredInClassesThat()
          .areAnnotatedWith(jakarta.persistence.Entity.class)
          .should()
          .haveRawType(LocalDateTime.class)
          .because("store instants as Instant/timestamptz");

  @ArchTest static final ArchRule noStdStreams = NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS;

  @ArchTest static final ArchRule noJul = NO_CLASSES_SHOULD_USE_JAVA_UTIL_LOGGING;
}
