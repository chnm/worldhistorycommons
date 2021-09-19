<?php

namespace Drupal\whc_migration\Plugin\migrate\process;

use Drupal\migrate\ProcessPluginBase;
use Drupal\migrate\MigrateException;
use Drupal\migrate\MigrateExecutableInterface;
use Drupal\migrate\Row;

/**
 * This plugin checks to see if node should be featured to the homepage.
 *
 * @MigrateProcessPlugin(
 *   id = "whcpromote"
 * )
 */
class whcPromote extends ProcessPluginBase {
  /**
   * {@inheritdoc}
   */

  public function transform($value, MigrateExecutableInterface $migrate_executable, Row $row, $destination_property) {

    $status = $value['value'];

    if ($status == 1) {
      $promote =  0;
    } else {
      $promote =  1;
    }

    return $value['value'] = $promote;

  }
}